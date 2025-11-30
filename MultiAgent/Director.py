from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.constants import START, END
from langchain_community.chat_models import ChatTongyi
from operator import add
from config.load_key import KeyLoader

from langgraph.graph import StateGraph

key_lodear = KeyLoader()
api_key = key_lodear.get_key("BAILIAN_API_KEY")

llm = ChatTongyi(
    model="qwen-plus",
    api_key=api_key
)

nodes = ["supervisor","travel","joke","other","couplet"]

class State(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add]
    type: str


def other_node(state: State):
    print(">>> other node")
    writer = get_stream_writer()
    writer({"node",">>>> other_node"})
    return {"messages":[HumanMessage(content="我暂时无法回答这个问题")], "type":"other"}

def supervisor_node(state: State):
    print(">>> supervisor node")
    writer = get_stream_writer()
    writer({"node", ">>>> supervisor_node"})
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
        writer({"supervisor_step", f"已经返回结果：{state['type']}智能体处理结果"})
        return {"type": END}
    else:
        response = llm.invoke(prompts)
        typeRes = response.content
        writer({"supervisor_step", f"问题结果分类：{typeRes}"})
        if typeRes in nodes:
            return {"type":typeRes}
        else:
            raise ValueError("type is not in (supervisor,travel,joke,other,couplet)")

    return {}

def travel_node(state: State):
    print(">>> travel node")
    writer = get_stream_writer()
    writer({"node",">>>> travel_node"})
    return {}

def joke_node(state: State):
    print(">>> joke node")
    writer = get_stream_writer()
    writer({"node",">>>> joke_node"})
    return {}

def couplet_node(state: State):
    print(">>> couplet node")
    writer = get_stream_writer()
    writer({"node",">>>> couplet_node"})
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

    for chunk in graph.stream({"messages":[HumanMessage(content="给我讲一个郭德纲的笑话")]}, config, stream_mode="custom"):
        print(chunk)
