"""Falco 事件字段的泛化规则。

容器画像要能跨实例比对，事件字段里随实例变化的部分就必须先折叠掉：同一张
画像在不同机器上会看到不同的 UUID、IP、日期、镜像哈希和 mktemp 后缀，原样
入树会让两棵树几乎不重合。这里把这些"具体取值"统一替换成固定占位符，只留
结构信息。

规则按顺序串联执行，前一条的输出是后一条的输入——顺序本身是语义的一部分，
例如日期必须先于长数字识别，否则 20240131 会被当成普通数字吃掉。
"""

import re

# (正则, 占位符)，按顺序执行
_PLACEHOLDER_RULES = (
    # UUID：标准带连字符形态，边界放宽以兼容嵌在路径中的情况
    (
        re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
        "<uuid>",
    ),
    # IPv4：逐段限幅，避免把版本号之类的短数字串误判成地址
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "<ip>",
    ),
    # 日期：文件名里的 YYYY-MM-DD / YYYYMMDD / YYYY_MM_DD
    (re.compile(r"(?<!\d)20\d{2}[-_]?\d{2}[-_]?\d{2}(?!\d)"), "<date>"),
    # 长哈希：md5/sha1/sha256 等，去掉 \b 以便命中嵌在路径里的情况
    (re.compile(r"(?<![g-zG-Z])[0-9a-fA-F]{32,}(?![g-zG-Z])"), "<hash>"),
    # 短十六进制串：用前后视断言保证不会切掉普通单词的一部分
    (re.compile(r"(?<![a-zA-Z])[0-9a-fA-F]{8,31}(?![a-zA-Z])"), "<hex>"),
    # 长数字串：端口之上的编号、inode、时间戳等
    (re.compile(r"(?<![a-zA-Z])\d{5,}(?![a-zA-Z])"), "<num>"),
    # mktemp 风格随机后缀：紧跟在点号之后的 6 位字母数字
    (re.compile(r"(?<=\.)[a-zA-Z0-9]{6}(?=$|/)"), "<random>"),
)


def tokenize_attribute(attr):
    """把属性值泛化成可跨实例比对的键。

    非字符串取值先转成字符串再泛化；空值（含 None、0、空串）原样返回，
    调用方据此判断"字段缺失"与"字段为空"是同一件事。
    """
    if not attr:
        return attr

    text = attr if isinstance(attr, str) else str(attr)
    for pattern, placeholder in _PLACEHOLDER_RULES:
        text = pattern.sub(placeholder, text)
    return text
