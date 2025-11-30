import json
from pathlib import Path
from typing import Optional


class KeyLoader:
    """API密钥加载器，用于从Keys.json文件中加载配置的密钥"""
    
    def __init__(self, keys_file: Optional[str] = None):
        """
        初始化密钥加载器
        
        Args:
            keys_file: Keys.json文件的路径，如果为None，则使用默认路径（同目录下的Keys.json）
        """
        if keys_file is None:
            # 获取当前文件所在目录
            current_dir = Path(__file__).parent
            keys_file = current_dir / "Keys.json"
        
        self.keys_file = Path(keys_file)
        self._keys = None
        self._load_keys()
    
    def _load_keys(self) -> None:
        """从JSON文件中加载所有密钥"""
        if not self.keys_file.exists():
            raise FileNotFoundError(f"密钥文件不存在: {self.keys_file}")
        
        try:
            with open(self.keys_file, 'r', encoding='utf-8') as f:
                self._keys = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"密钥文件格式错误: {e}")
        except Exception as e:
            raise IOError(f"读取密钥文件失败: {e}")
    
    def get_key(self, key_name: str, default: Optional[str] = None) -> str:
        """
        根据key名称获取对应的值
        
        Args:
            key_name: 要获取的key名称，例如 "BAILIAN_API_KEY"
            default: 如果key不存在时返回的默认值，如果为None则抛出异常
        
        Returns:
            对应的密钥值
        
        Raises:
            KeyError: 当key不存在且default为None时
        """
        if self._keys is None:
            self._load_keys()
        
        if key_name in self._keys:
            return self._keys[key_name]
        
        if default is not None:
            return default
        
        raise KeyError(f"密钥 '{key_name}' 在 {self.keys_file} 中不存在")
    
    def get_all_keys(self) -> dict:
        """
        获取所有已加载的密钥
        
        Returns:
            包含所有密钥的字典
        """
        if self._keys is None:
            self._load_keys()
        return self._keys.copy()
    
    def reload(self) -> None:
        """重新加载密钥文件（适用于文件更新后）"""
        self._keys = None
        self._load_keys()


# 创建全局实例，方便直接使用
_default_loader = None


def load_key(key_name: str, keys_file: Optional[str] = None, default: Optional[str] = None) -> str:
    """
    便捷函数：根据key名称加载对应的值
    
    Args:
        key_name: 要获取的key名称，例如 "BAILIAN_API_KEY"
        keys_file: Keys.json文件的路径，如果为None，则使用默认路径
        default: 如果key不存在时返回的默认值，如果为None则抛出异常
    
    Returns:
        对应的密钥值
    
    Examples:
        >>> api_key = load_key("BAILIAN_API_KEY")
        >>> api_key = load_key("OPENAI_API_KEY", default="default-key")
        >>> api_key = load_key("CUSTOM_KEY", keys_file="/path/to/custom/keys.json")
    """
    global _default_loader
    
    if keys_file is None:
        if _default_loader is None:
            _default_loader = KeyLoader()
        return _default_loader.get_key(key_name, default)
    else:
        loader = KeyLoader(keys_file)
        return loader.get_key(key_name, default)
