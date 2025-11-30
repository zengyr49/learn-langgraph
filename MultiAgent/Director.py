import asyncio
from operator import add
from typing import TypedDict, Annotated

from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.constants import START, END
from langgraph.graph import StateGraph

from config.load_key import KeyLoader

key_lodear = KeyLoader()
api_key = key_lodear.get_key("BAILIAN_API_KEY")

llm = ChatTongyi(
    model="qwen-plus",
    api_key=api_key
)

nodes = ["supervisor", "travel", "joke", "other", "couplet"]


class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add]
    type: str


def other_node(state: State):
    print(">>> other node")
    writer = get_stream_writer()
    writer({"node": ">>>> other_node"})
    return {"messages": [HumanMessage(content="我暂时无法回答这个问题")], "type": "other"}


def supervisor_node(state: State):
    print(">>> supervisor node")
    writer = get_stream_writer()
    writer({"node": ">>>> supervisor_node"})
    prompt = """你是一个专业的客服助手，负责对用户的问题进行分类，并将任务分给其他Agent执行。
        如果用户的问题是和旅行相关，则返回 travel。
        如果用户的问题是和笑话相关，则返回 joke。
        如果用户的问题是和对联相关，则返回 couplet。
        如果是其他问题，则返回 other。
        除了这几个选项，不要返回其他内容。
        """

    prompts = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": state["messages"][-1].content if state["messages"] else ""}
    ]

    # 检查是否已经有类型（表示是返回的循环）
    if state.get("type") and state["type"] != END:
        writer({"supervisor_step": f"已经返回结果：{state['type']}智能体处理结果"})
        return {"type": END}
    else:
        response = llm.invoke(prompts)
        typeRes = response.content
        writer({"supervisor_step": f"问题结果分类：{typeRes}"})
        if typeRes in nodes:
            return {"type": typeRes}
        else:
            raise ValueError("type is not in (supervisor,travel,joke,other,couplet)")

    return {}


# 旅行节点，用于教学mcp server调用的使用
async def travel_node(state: State):
    print(">>> travel node")
    writer = get_stream_writer()
    writer({"node": ">>>> travel_node"})

    # streamable http
    # client = MultiServerMCPClient({"amap-maps": {"url": "https://mcp.api-inference.modelscope.net/xxxxxxx/mcp",
    #                                                    "transport":"streamable_http"}})
    # stdio
    client = MultiServerMCPClient({"amap-maps": {
        "args": [
            "-y",
            "@amap/amap-maps-mcp-server"
        ],
        "transport": "stdio",
        "command": "npx",
        "env": {
            "AMAP_MAPS_API_KEY": ""
        }
    }})

    # 异步获取工具
    tools = await client.get_tools()
    agent = create_agent(model=llm, tools=tools)

    sys_prompt = "你是一个专业的旅行规划助手，根据用户的问题，生成一个旅游路线规划。使用中文回答，并返回不超过100字的回答"
    # 使用 LangChain 消息对象
    user_content = state["messages"][-1].content if state["messages"] else ""
    input_messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=user_content)
    ]

    # 使用异步调用
    response = await agent.ainvoke({"messages": input_messages})
    # agent 返回的是包含 messages 的字典，需要提取最后一条消息的内容
    response_messages = response.get("messages", [])
    if response_messages:
        last_message = response_messages[-1]
        content = last_message.content if hasattr(last_message, 'content') else str(last_message)
    else:
        content = "未能生成旅行规划"

    writer({"travel_result": content})
    return {"messages": [HumanMessage(content=content)], "type": "travel"}


def joke_node(state: State):
    print(">>> joke node")
    writer = get_stream_writer()
    writer({"node": ">>>> joke_node"})

    sys_prompt = "你是一个笑话大师，根据用户的问题写一个不超过100个字的笑话"
    # prompts = [
    #     {"role": "system", "content": sys_prompt},
    #     {"role": "user", "content": state["messages"][-1].content if state["messages"] else ""}
    # ]
    user_content = state["messages"][-1].content if state["messages"] else ""
    input_messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=user_content)
    ]
    response = llm.invoke(input_messages)
    writer({"joke_result": response.content})

    return {"messages": [HumanMessage(content=response.content)], "type": "joke"}


def couplet_node(state: State):
    print(">>> couplet node")
    writer = get_stream_writer()
    writer({"node": ">>>> couplet_node"})
    return {}


def routing_func(state: State):
    type_value = state.get("type", "")
    if type_value == "joke":
        return "joke_node"
    elif type_value == "travel":
        return "travel_node"
    elif type_value == "couplet":
        return "couplet_node"
    elif type_value == END:
        return END
    else:
        return "other_node"


builder = StateGraph(State)
# 加节点
builder.add_node("supervisor_node", supervisor_node)
builder.add_node("travel_node", travel_node)
builder.add_node("joke_node", joke_node)
builder.add_node("couplet_node", couplet_node)
builder.add_node("other_node", other_node)

# 加边
builder.add_edge(START, "supervisor_node")
builder.add_conditional_edges("supervisor_node", routing_func,
                              ["travel_node", "joke_node", "couplet_node", "other_node", END])
builder.add_edge("travel_node", "supervisor_node")
builder.add_edge("joke_node", "supervisor_node")
builder.add_edge("couplet_node", "supervisor_node")
builder.add_edge("other_node", "supervisor_node")

# 构建graph
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

if __name__ == '__main__':
    config = {
        "configurable": {
            "thread_id": "1"
        }
    }


    # 使用异步调用（比较晦涩，先看着吧）
    async def run_graph():
        async for chunk in graph.astream(
                {"messages": [HumanMessage(content="给我规划一条顺德美的总部大楼到佛山乾沣水疗的驾车路线")]},
                config,
                stream_mode="custom"
        ):
            print(chunk)


    # 运行异步函数
    asyncio.run(run_graph())

    # 如果使用 invoke 方法，可以这样：
    # async def run_invoke():
    #     res = await graph.ainvoke(
    #         {"messages":[HumanMessage(content="今天天气怎么样")]}, 
    #         config
    #     )
    #     print(res["messages"][-1].content)
    # asyncio.run(run_invoke())
