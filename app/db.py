from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .config import DATA_DIR, DEFAULT_SPEECH_SECONDS

DB_PATH = DATA_DIR / "practice.db"

SEED_CATEGORIES = [
    "临时场合",
    "描述物品",
    "介绍产品",
    "社交表达",
    "观点表达",
    "说服沟通",
    "职场沟通",
    "自我表达",
    "知识表达",
]

SEED_QUESTIONS = {
    "临时场合": [
        "你突然被邀请在朋友聚会上说几句话，请现场表达。",
        "会议临时让你补充一个观点，请立即发言。",
        "在活动现场被主持人点名分享感受，请临场回应。",
        "第一次加入新团队，请即兴介绍自己并表达期待。",
        "电梯里遇到重要客户，只有一分钟，你会怎么开启对话？",
        "老师突然请你上台总结这次活动，请现场组织语言。",
        "朋友临时让你帮忙主持一场小型生日会，请说开场词。",
        "旅行途中被问到“你为什么来这里”，请即兴回答。",
    ],
    "描述物品": [
        "描述你此刻身边最常见的一件物品，让听众在脑中形成画面。",
        "介绍一本最近读过的书，说清它最打动你的地方。",
        "描述一道你熟悉的菜，让人听完就理解它的味道和做法。",
        "介绍一个你去过的地方，让没去过的人产生兴趣。",
        "描述一件陪伴你很久的旧物，以及它对你的意义。",
        "向别人介绍你最常用的一件数码产品。",
        "描述你理想中的房间，让人感受到具体氛围。",
        "用三句话介绍你今天穿的一套衣服。",
    ],
    "介绍产品": [
        "向完全不了解的人介绍一个你常用的 App。",
        "向企业客户介绍一款能提升工作效率的软件。",
        "向家中长辈介绍一件智能家居产品。",
        "向朋友推荐一件你愿意反复购买的产品。",
        "向第一次接触的人介绍一款专业工具，并避免术语。",
        "向预算有限的客户介绍一款价格较高的产品。",
        "用生活场景说明一款产品解决的真实问题。",
        "向投资人概述一个产品想法：用户、价值和差异。",
    ],
    "社交表达": [
        "向刚认识的人做一段自然、不过分正式的自我介绍。",
        "在婚礼上向新人送上一段真诚祝福。",
        "朋友情绪低落时，说一段理解和鼓励的话。",
        "向最近帮助过你的人当面表达感谢。",
        "邀请一位很久没见的朋友参加周末活动。",
        "因为误会向朋友道歉，并说明你准备怎么修复。",
        "在家庭聚会上回应长辈对你工作的关心。",
        "第一次参加线下兴趣社群，请介绍自己并找到共同话题。",
    ],
    "观点表达": [
        "你认为早起是否一定比晚睡更高效？请给出观点。",
        "短视频让人的注意力变短了吗？请说明理由。",
        "年轻人应该先攒钱还是先投资自己？请表达立场。",
        "通勤时间是否会降低一个人的生活质量？",
        "工作中过程重要还是结果重要？请现场论述。",
        "是否应该把兴趣爱好发展成职业？请给出判断。",
        "公开表达前是否需要写逐字稿？请说明你的看法。",
        "选择城市生活时，机会和成本哪个更应该优先考虑？",
    ],
    "说服沟通": [
        "说服同事采用一种更高效但需要学习的新流程。",
        "说服朋友减少熬夜，并给出可执行的建议。",
        "向家人解释你想换一份工作的原因。",
        "向领导争取一项项目预算。",
        "委婉拒绝同事临时转交给你的额外任务。",
        "让团队接受一个短期麻烦、长期收益的方案。",
        "说服一个犹豫的人参加公开表达训练。",
        "在意见冲突时，让双方先同意一个问题解决框架。",
    ],
    "职场沟通": [
        "如何向领导汇报一个进展不顺的项目？",
        "同事在会议上频繁打断你，你会如何当场回应？",
        "如何向跨部门同事说明一个复杂需求并争取配合？",
        "如何委婉拒绝一个你无法按时完成的任务？",
        "向团队宣布一个不受欢迎但必须执行的决定。",
        "在复盘会上承认自己的失误，同时给出改进方案。",
        "向新同事介绍你的岗位职责和协作边界。",
        "领导临时追问一个你还没准备好的数据，你会怎么回应？",
    ],
    "自我表达": [
        "介绍一个最近让你发生改变的经历。",
        "如果重新选择一次，你会改变哪个决定？为什么？",
        "用具体事例说明你最有优势的一种能力。",
        "讲一次失败经历，以及它给你留下的长期影响。",
        "描述你理想中的一天，从早晨到夜晚。",
        "分享一个你很感谢，却很少当面表达的人。",
        "说说你正在坚持的一件事，以及最难的地方。",
        "如果五年后的你给现在的你一句建议，会是什么？",
    ],
    "知识表达": [
        "用一个生活案例解释“复利效应”。",
        "用通俗语言讲清楚“机会成本”这个概念。",
        "向朋友说明睡眠为什么重要。",
        "解释一个你最近学到并真正用上的知识点。",
        "用三句话说明什么是“幸存者偏差”。",
        "向小学生解释为什么天空是蓝色的。",
        "用一个比喻解释数据库索引的作用。",
        "解释“边际成本”以及它如何影响日常决策。",
    ],
}

KNOWLEDGE_SEED = {
    "心理与行为": [
        (
            "破窗效应",
            "环境中的小失序如果不被处理，可能诱导更多失序行为。",
            "现象：一扇窗户破了没人修，其他窗户也更容易被破坏。\n原理：可见的失序会降低人们对规则的重视，并传递“大家都这样做”的信号。\n例子：公共区域出现第一件垃圾后，后续乱扔现象可能变多；团队流程出现小漏洞后，也可能逐渐被忽视。\n口述提示：先讲一个具体场景，再说明它如何改变人的判断，最后给出及时修复小问题的建议。",
        ),
        (
            "旁观者效应",
            "在场的人越多，个体越可能觉得自己不需要出手。",
            "现象：有人需要帮助时，周围人很多，却可能没有人行动。\n原理：责任被分散，人们还会观察他人的反应，希望先确认自己是否应该介入。\n例子：街头有人突然不适，如果只喊“谁来帮帮忙”，响应可能很少；明确指向某个人求助，成功率通常更高。\n口述提示：可从真实场景切入，强调不是道德冷漠，而是责任分散，再给出明确求助的方法。",
        ),
        (
            "锚定效应",
            "最先接触到的信息会像锚一样影响后续判断。",
            "现象：同一件商品先标高价再打折，会让人觉得折扣价更划算。\n原理：人在判断数值或可能性时，容易把最初接触到的信息作为参照，即使这个参照并不合理。\n例子：谈判时先提出报价的一方，往往会给后续讨论设定范围。\n口述提示：解释“第一印象会变成比较尺子”，再用价格、谈判或时间估算说明影响。",
        ),
    ],
    "经济与管理": [
        (
            "复利效应",
            "收益持续投入后，增长会由本金和已有收益共同推动。",
            "现象：早期增长看似缓慢，时间拉长后曲线明显上扬。\n原理：每一轮新增结果都会成为下一轮增长的基数。\n例子：知识、技能、储蓄和用户口碑都可能产生复利；每天进步一点，长期差距来自积累而非单次爆发。\n口述提示：用“雪球越滚越大”建立画面，再提醒复利也适用于负面习惯。",
        ),
        (
            "机会成本",
            "选择一种方案时，放弃掉的最佳替代方案就是它的机会成本。",
            "现象：时间花在加班上，可能意味着放弃陪伴家人、运动或学习。\n原理：资源有限，任何选择都意味着无法同时选择其他用途。\n例子：是否读研、是否接一份工作、周末如何安排，都可以用机会成本比较。\n口述提示：不要说“成本只是花了多少钱”，重点讲清被放弃的最佳选择。",
        ),
        (
            "飞轮效应",
            "持续推动一个系统跨过临界点后，它会越来越容易自行运转。",
            "现象：飞轮起初很难推动，但每一圈都会积累动能。\n原理：多个环节互相增强，前期投入会形成后续优势。\n例子：好产品带来满意用户，用户口碑又带来更多用户，更多使用数据继续改善产品。\n口述提示：按“初始很慢—环节互推—越过临界点—加速运转”的顺序讲。",
        ),
    ],
    "科学原理": [
        (
            "浮力",
            "液体或气体对浸入其中的物体产生向上的托力。",
            "现象：木头漂在水面，铁块通常下沉，游泳时身体也会感到被水托住。\n原理：物体排开流体后，流体不同深度的压力差形成向上的合力。\n例子：轮船用空腔排开大量水，因此巨大的钢制船体仍能浮起来。\n口述提示：从“水里托着手”的感觉讲起，再解释排开液体和压力差。",
        ),
        (
            "杠杆",
            "借助支点和力臂，小力可以撬动更大的阻力。",
            "现象：用长扳手拧紧螺栓，通常比短扳手省力。\n原理：杠杆平衡取决于力的大小和力臂长度，力臂越长，需要的力越小。\n例子：跷跷板、开瓶器、手推车和剪刀都运用了杠杆结构。\n口述提示：先说省力现象，再讲支点、动力臂和阻力臂三个要素。",
        ),
        (
            "热传导",
            "热量会从温度较高的位置传向温度较低的位置。",
            "现象：金属勺放进热汤后，勺柄很快也会变热。\n原理：微观粒子通过碰撞和振动传递能量，材料不同，导热速度也不同。\n例子：金属锅善于导热，木质或塑料锅柄则用来减少热量传到手上。\n口述提示：用“热量从热处走向冷处”作为一句话结论，再举厨房中的例子。",
        ),
    ],
    "机器原理": [
        (
            "微波炉的工作原理",
            "微波让食物中的水分子快速振动，从而产生热量。",
            "现象：食物加热很快，但金属器皿可能打火，容器本身通常不会像食物一样变热。\n原理：磁控管产生微波，微波在炉腔内反射并被食物吸收，水分子振动摩擦后把能量转化为热。\n例子：热剩饭时，食物内部和外部会同时受热；金属反射微波，所以不能随意放入。\n口述提示：抓住“微波不是直接变出热，而是让水分子运动”这一核心。",
        ),
        (
            "冰箱的工作原理",
            "冰箱通过搬运热量，把箱内热量排到箱外。",
            "现象：冰箱背后或侧面摸起来会发热，冷冻室却能持续保持低温。\n原理：压缩机推动制冷剂循环，制冷剂蒸发吸热、冷凝放热，利用物态变化搬运热量。\n例子：打开冰箱门不会让房间整体变凉，因为冰箱只是把热量从内部搬到外部并额外产生热量。\n口述提示：不要只说“制造冷气”，要强调它是在把热量从里面搬到外面。",
        ),
        (
            "空调的工作原理",
            "空调把室内的热量搬到室外，从而降低室内温度。",
            "现象：空调室内机吹出冷风，室外机同时排出热量。\n原理：制冷剂在室内机蒸发吸热，在室外机冷凝放热，压缩机负责推动整个循环。\n例子：冬季制热时，许多热泵空调会反向运行，把室外热量搬进室内。\n口述提示：用“搬运热量而不是凭空制造冷”作为主线，再补充制热时的反向循环。",
        ),
    ],
}


KNOWLEDGE_SEED_ORDER = [
    "心理与行为",
    "经济与管理",
    "科学原理",
    "机器原理",
    "计算机与网络",
    "人体与健康",
]

KNOWLEDGE_ADDITIONS = {
    "心理与行为": [
        (
            "损失厌恶",
            "失去一样东西带来的痛苦，通常大于得到同样东西带来的快乐。",
            "现象：同样金额的损失和收益，损失往往更让人难受。\n原理：人在决策时会重点回避损失，而不只是追求收益最大化。\n例子：免费试用结束后，人们往往不愿放弃已经习惯的服务；押金制度也更容易促使守约。\n口述提示：用“丢一百元和捡一百元感受不同”作为开场，再讲决策影响。",
        ),
        (
            "峰终定律",
            "人们对一段经历的整体评价，主要受高峰时刻和结束时刻影响。",
            "现象：一次体验大部分时间都不错，但结尾很糟，回忆往往仍然很差。\n原理：记忆会压缩过程，重点保留情绪最强的瞬间和最后感受。\n例子：排队时间很长，但入口前体验有趣、离场又有惊喜，整体评价可能反而更高。\n口述提示：先说“人记住的不是平均体验”，再举服务、演讲或旅行中的例子。",
        ),
        (
            "确认偏误",
            "人更容易寻找和相信支持自己原有观点的信息。",
            "现象：同一份资料，立场不同的人会注意不同部分。\n原理：大脑倾向于维护已有判断，并降低冲突信息的权重。\n例子：只看符合自己观点的账号、只搜索支持自己的证据，都可能让判断越来越单一。\n口述提示：解释它如何形成信息茧房，再给出主动寻找反方证据的方法。",
        ),
        (
            "福格行为模型",
            "一个行为发生，需要动机、能力和触发条件同时具备。",
            "现象：明知一件事重要，却经常迟迟不做。\n原理：动机不足、行为太难或没有合适提醒，任何一项缺失都可能让行动失败。\n例子：想养成喝水习惯，可以把水杯放在眼前，并降低每次喝水的难度。\n口述提示：用“想做、能做、被提醒”三个条件说明行为设计。",
        ),
    ],
    "经济与管理": [
        (
            "边际效用递减",
            "同一件东西消费得越多，每增加一份带来的满足感通常越低。",
            "现象：非常饿时第一个包子最香，吃到后面满足感逐渐下降。\n原理：需求强度会随着已获得的数量增加而降低。\n例子：促销常强调第一杯、第一件，因为重复消费的额外吸引力会下降。\n口述提示：从吃包子或喝饮料的生活体验切入，再联系定价和决策。",
        ),
        (
            "帕累托法则",
            "很多结果并不平均，少数关键因素往往贡献大部分产出。",
            "现象：20% 的客户可能贡献 80% 的收入，少量问题可能造成大部分故障。\n原理：资源、注意力和结果通常呈不均匀分布。\n例子：工作中先处理影响最大的关键任务，往往比平均用力更有效。\n口述提示：强调它不是精确的数学定律，而是一种寻找关键少数的方法。",
        ),
        (
            "网络效应",
            "使用产品或服务的人越多，每个用户获得的价值可能越高。",
            "现象：社交平台的用户越多，可联系的人和内容越丰富。\n原理：新增用户会提升整个网络的连接价值和吸引力，形成正反馈。\n例子：通信软件、电商平台和操作系统都可能受益于网络效应。\n口述提示：用“越多人用，越好用”概括，再解释它为什么容易形成领先优势。",
        ),
        (
            "供需关系",
            "价格和数量会受到供给与需求力量共同影响。",
            "现象：某种商品突然受欢迎时价格可能上涨，供应增加后价格又可能回落。\n原理：买方愿意购买的数量和卖方愿意提供的数量，会随价格变化。\n例子：节假日需求增加，酒店和交通价格往往上涨；供应恢复后价格可能下降。\n口述提示：用“想买的人”和“愿意卖的人”两边变化解释价格。",
        ),
    ],
    "科学原理": [
        (
            "惯性",
            "物体倾向于保持原来的静止或运动状态。",
            "现象：公交车突然刹车时，人会继续向前倾。\n原理：物体质量越大，改变运动状态所需的力通常越大。\n例子：系安全带可以减少急刹车时身体继续向前运动造成的伤害。\n口述提示：从坐车体验切入，再说明惯性不是一种推力，而是物体保持状态的倾向。",
        ),
        (
            "大气压",
            "空气虽然看不见，但会对周围物体产生压力。",
            "现象：吸盘能贴在墙上，用吸管可以把饮料吸入口中。\n原理：内部气压降低后，外部较大的大气压会把物体压向另一侧或推动液体上升。\n例子：抽走杯子里的部分空气，杯口的气球可能被压进杯中。\n口述提示：强调不是吸管“把水拉上来”，而是外界大气压把水推上来。",
        ),
        (
            "声音传播",
            "声音需要通过介质振动传播，真空里无法传播。",
            "现象：敲击桌面时，桌面的振动会引起空气振动。\n原理：振动带动周围介质形成疏密变化，最终传递到耳朵。\n例子：把耳朵贴在铁轨上能更早听到远处振动，因为固体传声通常比空气更快。\n口述提示：按“振动—介质—耳朵”的顺序解释，并说明真空为什么听不到声音。",
        ),
        (
            "虹吸现象",
            "液体可以借助重力越过较高处，持续流向更低处。",
            "现象：装满水的软管两端分别放在高低两个容器中，水会自动流下。\n原理：重力与管内压力差共同推动液体流动。\n例子：给鱼缸换水时，可以用软管把水引到更低的水桶。\n口述提示：先强调液体最终流向更低处，再解释管内压力差的作用。",
        ),
    ],
    "机器原理": [
        (
            "洗衣机的工作原理",
            "洗衣机通过水流、摩擦和旋转带走衣物上的污渍。",
            "现象：滚筒不断转动，衣物在水流中反复翻滚。\n原理：洗涤剂降低污渍与纤维的结合力，机械运动把污渍分散到水中，脱水时高速旋转利用离心作用排走水分。\n例子：波轮洗衣机依靠底部波轮制造强水流，滚筒洗衣机则把衣物带到高处后落下。\n口述提示：按“浸润—分离污渍—漂洗—离心脱水”的顺序说明。",
        ),
        (
            "电梯的工作原理",
            "电梯通过曳引系统平衡轿厢和配重，实现平稳升降。",
            "现象：电梯里有沉重轿厢，却能以相对较小的动力平稳移动。\n原理：钢缆绕过曳引轮，轿厢与配重相互平衡，电机主要克服重量差和摩擦。\n例子：多层建筑中的客梯还依靠限速器、安全钳和制动器保证停靠与安全。\n口述提示：抓住“平衡和牵引”两个关键词，不要只讲电机拉上去。",
        ),
        (
            "扫地机器人的工作原理",
            "扫地机器人通过感知环境、规划路径和控制清扫部件自主移动。",
            "现象：它会在房间里移动、避开障碍并寻找充电座。\n原理：传感器采集距离和位置信息，控制程序建立地图并规划路线，电机驱动车轮和刷盘。\n例子：激光雷达、视觉摄像头或碰撞传感器可以帮助它判断墙边和家具位置。\n口述提示：按“感知—决策—执行”三步解释，这也能代表许多机器人系统。",
        ),
    ],
    "计算机与网络": [
        (
            "数据库索引",
            "数据库索引用额外结构加快查找，类似书的目录。",
            "现象：给大量数据建立索引后，查询常常更快。\n原理：索引维护有序或可快速定位的数据结构，避免逐行扫描整张表。\n例子：按姓名查电话簿，先查目录显然比从第一页开始快。\n口述提示：同时说明索引会占用空间，并让新增和修改数据变慢。",
        ),
        (
            "缓存",
            "缓存把常用数据放在更快的存储位置，减少重复计算或远程读取。",
            "现象：第二次打开网页或应用，内容常常比第一次更快。\n原理：把近期高频使用的数据临时保存，下一次先检查缓存是否命中。\n例子：浏览器缓存图片，应用缓存用户资料，数据库缓存查询结果。\n口述提示：用“把常用工具放在手边”解释，再提缓存过期和数据一致性问题。",
        ),
        (
            "DNS 解析",
            "DNS 把便于记忆的域名转换成计算机使用的 IP 地址。",
            "现象：访问网站时输入网址，而不是输入一串数字地址。\n原理：设备先向 DNS 服务器查询域名对应的 IP，再用该地址连接目标服务器。\n例子：就像先在通讯录中找到姓名对应的电话号码，再拨号联系。\n口述提示：用“互联网通讯录”作为核心比喻，并补充缓存会加快解析。",
        ),
        (
            "对称与非对称加密",
            "对称加密用同一把钥匙，非对称加密用公钥和私钥配合。",
            "现象：安全网站、消息软件和数字签名都依赖加密。\n原理：对称加密速度快，但需要安全分发密钥；非对称加密便于公开公钥，但计算更慢。\n例子：实际系统常用非对称方式交换密钥，再用对称加密传输大量数据。\n口述提示：用“普通锁”和“公开锁”做类比，避免只讲术语。",
        ),
    ],
    "人体与健康": [
        (
            "睡眠周期",
            "睡眠会在浅睡、深睡和快速眼动等多个阶段之间循环。",
            "现象：夜间会短暂醒来，早晨常从一个睡眠周期附近自然醒来。\n原理：大脑和身体在不同阶段承担记忆巩固、恢复和情绪调节等任务。\n例子：固定起床时间通常比追求绝对睡眠总时长更稳定。\n口述提示：说明睡眠不是一条直线，而是一轮轮循环。",
        ),
        (
            "生物钟",
            "人体内部节律会让激素、体温和警觉度在一天中规律变化。",
            "现象：同样睡七小时，固定作息和昼夜颠倒后的感受可能不同。\n原理：光线、进食和活动等信号会校准内部节律。\n例子：早上接触自然光、晚上减少强光，有助于稳定睡眠节律。\n口述提示：用“身体自带的时间程序”解释，再讲光照为什么重要。",
        ),
        (
            "免疫记忆",
            "免疫系统遇到过某些病原体后，会保留更快的识别和反应能力。",
            "现象：得过某些感染后短期内不容易再次感染同一病原体。\n原理：特定免疫细胞会保留记忆，再次遇到目标时能更快产生抗体或杀伤反应。\n例子：疫苗利用这一机制，让身体在不经历重症的情况下提前建立保护。\n口述提示：按“第一次识别—保留记忆—第二次快速反应”说明。",
        ),
        (
            "有氧运动与心率",
            "持续、有节律的运动会让心脏和呼吸系统更高效地供氧。",
            "现象：运动时心率上升、呼吸加快，长期训练后静息心率可能下降。\n原理：心肌更强、毛细血管更丰富，身体运输和利用氧气的效率提高。\n例子：快走、慢跑、骑行和游泳都可以进行有氧训练，强度应按个人情况控制。\n口述提示：强调强度因人而异，不要给出固定心率数字或医疗建议。",
        ),
    ],
}

class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        self._seed()
        self.conn.commit()

    def _create_schema(self) -> None:
        with self._lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    text TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'research',
                    research_started_at TEXT,
                    research_ended_at TEXT,
                    speech_started_at TEXT,
                    speech_ended_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS outlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL UNIQUE,
                    content TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL UNIQUE,
                    text TEXT NOT NULL,
                    audio_path TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL UNIQUE,
                    scores_json TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    is_seed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(category_id) REFERENCES knowledge_categories(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS speech_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    start_ms INTEGER NOT NULL DEFAULT 0,
                    end_ms INTEGER NOT NULL DEFAULT 0,
                    text TEXT NOT NULL DEFAULT '',
                    unclear INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL UNIQUE,
                    checklist_json TEXT NOT NULL DEFAULT '{}',
                    reflection TEXT NOT NULL DEFAULT '',
                    completed_at TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_questions_enabled ON questions(enabled);
                CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
                CREATE INDEX IF NOT EXISTS idx_knowledge_items_category ON knowledge_items(category_id);
                CREATE INDEX IF NOT EXISTS idx_speech_segments_session ON speech_segments(session_id, position);
                """
            )
            self._ensure_session_columns()

    def _ensure_session_columns(self) -> None:
        columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        additions = {
            "mode": "TEXT NOT NULL DEFAULT 'research'",
            "topic_text": "TEXT NOT NULL DEFAULT ''",
            "material_snapshot": "TEXT NOT NULL DEFAULT ''",
            "speech_cues": "TEXT NOT NULL DEFAULT ''",
            "knowledge_item_id": "INTEGER",
            "speech_duration_seconds": f"INTEGER NOT NULL DEFAULT {DEFAULT_SPEECH_SECONDS}",
            "prep_started_at": "TEXT",
            "prep_ended_at": "TEXT",
            "review_started_at": "TEXT",
            "completed_at": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                self.conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {definition}")

    def _seed(self) -> None:
        with self._lock, self.conn:
            for index, name in enumerate(SEED_CATEGORIES):
                self.conn.execute(
                    "INSERT OR IGNORE INTO categories(name, sort_order) VALUES(?, ?)",
                    (name, index),
                )
            for category_name, questions in SEED_QUESTIONS.items():
                row = self.conn.execute(
                    "SELECT id FROM categories WHERE name = ?", (category_name,)
                ).fetchone()
                if row is None:
                    continue
                for text in questions:
                    exists = self.conn.execute(
                        "SELECT 1 FROM questions WHERE text = ?", (text,)
                    ).fetchone()
                    if exists is None:
                        self.conn.execute(
                            "INSERT INTO questions(category_id, text, enabled) VALUES(?, ?, 1)",
                            (row["id"], text),
                        )

            self._seed_knowledge_library()

    def _seed_knowledge_library(self) -> None:
        # Existing installations used the narrower name. Preserve all items while
        # migrating the category in place.
        old_category = self.conn.execute(
            "SELECT id FROM knowledge_categories WHERE name = '电器原理'"
        ).fetchone()
        machine_category = self.conn.execute(
            "SELECT id FROM knowledge_categories WHERE name = '机器原理'"
        ).fetchone()
        if old_category and not machine_category:
            self.conn.execute(
                "UPDATE knowledge_categories SET name = '机器原理' WHERE id = ?",
                (old_category["id"],),
            )
        elif old_category and machine_category:
            self.conn.execute(
                "UPDATE knowledge_items SET category_id = ? WHERE category_id = ?",
                (machine_category["id"], old_category["id"]),
            )
            self.conn.execute("DELETE FROM knowledge_categories WHERE id = ?", (old_category["id"],))

        version = self.conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'knowledge_seed_version'"
        ).fetchone()
        if version and int(version["value"]) >= 3:
            return

        for index, category_name in enumerate(KNOWLEDGE_SEED_ORDER):
            self.conn.execute(
                "INSERT OR IGNORE INTO knowledge_categories(name, sort_order) VALUES(?, ?)",
                (category_name, index),
            )
            category = self.conn.execute(
                "SELECT id FROM knowledge_categories WHERE name = ?", (category_name,)
            ).fetchone()
            items = KNOWLEDGE_SEED.get(category_name, []) + KNOWLEDGE_ADDITIONS.get(category_name, [])
            for title, summary, content in items:
                exists = self.conn.execute(
                    "SELECT 1 FROM knowledge_items WHERE title = ?", (title,)
                ).fetchone()
                if exists is None:
                    self.conn.execute(
                        "INSERT INTO knowledge_items(category_id, title, summary, content, is_seed) VALUES(?, ?, ?, ?, 1)",
                        (category["id"], title, summary, content),
                    )
        self.conn.execute(
            "INSERT INTO app_metadata(key, value) VALUES('knowledge_seed_version', '3') "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        )

    def _rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def _row(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        with self._lock:
            cur = self.conn.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _write(self, sql: str, params: tuple = ()) -> int:
        with self._lock, self.conn:
            cur = self.conn.execute(sql, params)
            return cur.lastrowid

    # ---- question bank ----
    def list_categories(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM categories ORDER BY sort_order, id")

    def create_category(self, name: str) -> dict[str, Any]:
        self._write(
            "INSERT OR IGNORE INTO categories(name, sort_order) VALUES(?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM categories))",
            (name,),
        )
        return self._row("SELECT * FROM categories WHERE name = ?", (name,))

    def delete_category(self, category_id: int) -> None:
        self._write("DELETE FROM categories WHERE id = ?", (category_id,))

    def list_questions(self, category_id: int | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT q.*, c.name AS category_name FROM questions q "
            "LEFT JOIN categories c ON c.id = q.category_id WHERE 1=1"
        )
        params: list[Any] = []
        if category_id is not None:
            sql += " AND q.category_id = ?"
            params.append(category_id)
        sql += " ORDER BY q.id DESC"
        return self._rows(sql, tuple(params))

    def get_question(self, question_id: int) -> dict[str, Any] | None:
        return self._row(
            "SELECT q.*, c.name AS category_name FROM questions q "
            "LEFT JOIN categories c ON c.id = q.category_id WHERE q.id = ?",
            (question_id,),
        )

    def create_question(self, text: str, category_id: int | None) -> dict[str, Any]:
        qid = self._write(
            "INSERT INTO questions(category_id, text, enabled) VALUES(?, ?, 1)",
            (category_id, text),
        )
        return self.get_question(qid)

    def update_question(
        self,
        question_id: int,
        text: str | None,
        category_id: int | None,
        enabled: bool | None,
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = []
        if text is not None:
            fields.append("text = ?")
            params.append(text)
        if category_id is not None:
            fields.append("category_id = ?")
            params.append(category_id)
        if enabled is not None:
            fields.append("enabled = ?")
            params.append(1 if enabled else 0)
        if fields:
            params.append(question_id)
            self._write(f"UPDATE questions SET {', '.join(fields)} WHERE id = ?", tuple(params))
        return self.get_question(question_id)

    def delete_question(self, question_id: int) -> None:
        self._write("DELETE FROM questions WHERE id = ?", (question_id,))

    def random_question(self) -> dict[str, Any] | None:
        return self._row(
            "SELECT q.*, c.name AS category_name FROM questions q "
            "LEFT JOIN categories c ON c.id = q.category_id "
            "WHERE q.enabled = 1 ORDER BY RANDOM() LIMIT 1"
        )

    # ---- sessions ----
    def create_session(
        self,
        mode: str,
        question_id: int | None,
        topic_text: str,
        material_snapshot: str,
        knowledge_item_id: int | None,
        speech_duration_seconds: int,
    ) -> dict[str, Any]:
        status = "prep" if mode == "improv" else "research"
        started_field = "prep_started_at" if mode == "improv" else "research_started_at"
        sid = self._write(
            f"INSERT INTO sessions(question_id, status, mode, topic_text, material_snapshot, "
            f"knowledge_item_id, speech_duration_seconds, {started_field}) "
            f"VALUES(?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                question_id,
                status,
                mode,
                topic_text,
                material_snapshot,
                knowledge_item_id,
                speech_duration_seconds,
            ),
        )
        return self.get_session(sid)

    def get_session(self, session_id: int) -> dict[str, Any] | None:
        row = self._row(
            "SELECT s.*, q.text AS question_text, c.name AS category_name, "
            "ki.title AS knowledge_title FROM sessions s "
            "LEFT JOIN questions q ON q.id = s.question_id "
            "LEFT JOIN categories c ON c.id = q.category_id "
            "LEFT JOIN knowledge_items ki ON ki.id = s.knowledge_item_id "
            "WHERE s.id = ?",
            (session_id,),
        )
        if row is None:
            return None
        row["notes"] = self.get_notes(session_id)
        row["outline"] = self.get_outline(session_id)
        row["transcript"] = self.get_transcript(session_id)
        row["segments"] = self.list_speech_segments(session_id)
        row["review"] = self.get_review(session_id)
        return row

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT s.*, q.text AS question_text, c.name AS category_name, "
            "ki.title AS knowledge_title FROM sessions s "
            "LEFT JOIN questions q ON q.id = s.question_id "
            "LEFT JOIN categories c ON c.id = q.category_id "
            "LEFT JOIN knowledge_items ki ON ki.id = s.knowledge_item_id "
            "ORDER BY s.id DESC LIMIT ?",
            (limit,),
        )
        for row in rows:
            transcript = self._row(
                "SELECT audio_path FROM transcripts WHERE session_id = ?", (row["id"],)
            )
            row["has_audio"] = bool(transcript and transcript.get("audio_path"))
            row["unclear_count"] = self._row(
                "SELECT COUNT(*) AS count FROM speech_segments WHERE session_id = ? AND unclear = 1",
                (row["id"],),
            )["count"]
        return rows

    def delete_session(self, session_id: int) -> dict[str, Any] | None:
        with self._lock, self.conn:
            session = self.conn.execute(
                "SELECT id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return None
            transcript = self.conn.execute(
                "SELECT audio_path FROM transcripts WHERE session_id = ?", (session_id,)
            ).fetchone()
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return {"audio_path": transcript["audio_path"] if transcript else None}

    def set_session_field(self, session_id: int, field: str, value: Any) -> None:
        allowed = {
            "prep_started_at",
            "prep_ended_at",
            "research_started_at",
            "research_ended_at",
            "speech_started_at",
            "speech_ended_at",
            "review_started_at",
            "completed_at",
            "status",
        }
        if field not in allowed:
            raise ValueError("非法字段")
        self._write(f"UPDATE sessions SET {field} = ? WHERE id = ?", (value, session_id))

    def update_session_status(self, session_id: int, status: str) -> None:
        self._write("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))

    # ---- notes and user outline ----
    def save_outline(self, session_id: int, content: str) -> str:
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM outlines WHERE session_id = ?", (session_id,))
            self.conn.execute(
                "INSERT INTO outlines(session_id, content) VALUES(?, ?)",
                (session_id, content),
            )
        return content

    def get_outline(self, session_id: int) -> str:
        row = self._row(
            "SELECT content FROM outlines WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        return row["content"] if row else ""

    def save_notes(self, session_id: int, content: str) -> str:
        self._write(
            "INSERT INTO notes(session_id, content) VALUES(?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET content = excluded.content, updated_at = CURRENT_TIMESTAMP",
            (session_id, content),
        )
        return content

    def save_speech_cues(self, session_id: int, content: str) -> str:
        self._write(
            "UPDATE sessions SET speech_cues = ? WHERE id = ?",
            (content, session_id),
        )
        return content

    def get_notes(self, session_id: int) -> str:
        row = self._row("SELECT content FROM notes WHERE session_id = ?", (session_id,))
        return row["content"] if row else ""

    # ---- transcript and sentence timeline ----
    def save_speech(
        self,
        session_id: int,
        text: str,
        audio_path: str | None,
        segments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO transcripts(session_id, text, audio_path) VALUES(?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET text = excluded.text, "
                "audio_path = COALESCE(excluded.audio_path, transcripts.audio_path), "
                "created_at = CURRENT_TIMESTAMP",
                (session_id, text, audio_path),
            )
            self.conn.execute("DELETE FROM speech_segments WHERE session_id = ?", (session_id,))
            self._insert_segments(session_id, segments)
            self.conn.execute(
                "UPDATE sessions SET speech_ended_at = COALESCE(speech_ended_at, CURRENT_TIMESTAMP), "
                "review_started_at = COALESCE(review_started_at, CURRENT_TIMESTAMP), status = 'review' "
                "WHERE id = ?",
                (session_id,),
            )
        return self.get_session(session_id)

    def _insert_segments(self, session_id: int, segments: list[dict[str, Any]]) -> None:
        for position, segment in enumerate(segments):
            text = str(segment.get("text", "")).strip()
            if not text:
                continue
            start_ms = max(0, int(segment.get("start_ms", 0) or 0))
            end_ms = max(start_ms, int(segment.get("end_ms", start_ms) or start_ms))
            self.conn.execute(
                "INSERT INTO speech_segments(session_id, position, start_ms, end_ms, text, unclear, note) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    position,
                    start_ms,
                    end_ms,
                    text,
                    1 if segment.get("unclear") else 0,
                    str(segment.get("note", "") or ""),
                ),
            )

    def list_speech_segments(self, session_id: int) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM speech_segments WHERE session_id = ? ORDER BY position, id",
            (session_id,),
        )

    def get_transcript(self, session_id: int) -> dict[str, Any] | None:
        return self._row("SELECT * FROM transcripts WHERE session_id = ?", (session_id,))

    # ---- review ----
    def save_review(
        self,
        session_id: int,
        segments: list[dict[str, Any]],
        checklist: dict[str, Any],
        reflection: str,
        complete: bool,
    ) -> dict[str, Any] | None:
        text = "\n".join(
            str(segment.get("text", "")).strip()
            for segment in segments
            if str(segment.get("text", "")).strip()
        )
        with self._lock, self.conn:
            transcript = self.conn.execute(
                "SELECT 1 FROM transcripts WHERE session_id = ?", (session_id,)
            ).fetchone()
            if transcript:
                self.conn.execute(
                    "UPDATE transcripts SET text = ? WHERE session_id = ?", (text, session_id)
                )
            elif text:
                self.conn.execute(
                    "INSERT INTO transcripts(session_id, text) VALUES(?, ?)", (session_id, text)
                )
            self.conn.execute("DELETE FROM speech_segments WHERE session_id = ?", (session_id,))
            self._insert_segments(session_id, segments)
            self.conn.execute(
                "INSERT INTO reviews(session_id, checklist_json, reflection, completed_at) "
                "VALUES(?, ?, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END) "
                "ON CONFLICT(session_id) DO UPDATE SET checklist_json = excluded.checklist_json, "
                "reflection = excluded.reflection, "
                "completed_at = CASE WHEN ? THEN COALESCE(reviews.completed_at, CURRENT_TIMESTAMP) ELSE reviews.completed_at END, "
                "updated_at = CURRENT_TIMESTAMP",
                (
                    session_id,
                    json.dumps(checklist, ensure_ascii=False),
                    reflection,
                    1 if complete else 0,
                    1 if complete else 0,
                ),
            )
            if complete:
                self.conn.execute(
                    "UPDATE sessions SET status = 'done', completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP) WHERE id = ?",
                    (session_id,),
                )
            elif self._session_status(session_id) not in {"done"}:
                self.conn.execute(
                    "UPDATE sessions SET status = 'review', review_started_at = COALESCE(review_started_at, CURRENT_TIMESTAMP) WHERE id = ?",
                    (session_id,),
                )
        return self.get_session(session_id)

    def _session_status(self, session_id: int) -> str:
        row = self.conn.execute("SELECT status FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row["status"] if row else ""

    def get_review(self, session_id: int) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM reviews WHERE session_id = ?", (session_id,))
        if row is None:
            return None
        try:
            row["checklist"] = json.loads(row.get("checklist_json") or "{}")
        except json.JSONDecodeError:
            row["checklist"] = {}
        return row

    # ---- local knowledge library ----
    def list_knowledge_categories(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT kc.*, COUNT(ki.id) AS item_count FROM knowledge_categories kc "
            "LEFT JOIN knowledge_items ki ON ki.category_id = kc.id "
            "GROUP BY kc.id ORDER BY kc.sort_order, kc.id"
        )

    def create_knowledge_category(self, name: str) -> dict[str, Any]:
        self._write(
            "INSERT OR IGNORE INTO knowledge_categories(name, sort_order) "
            "VALUES(?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM knowledge_categories))",
            (name,),
        )
        return self._row("SELECT * FROM knowledge_categories WHERE name = ?", (name,))

    def delete_knowledge_category(self, category_id: int) -> None:
        self._write("DELETE FROM knowledge_categories WHERE id = ?", (category_id,))

    def list_knowledge_items(self, category_id: int | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT ki.*, kc.name AS category_name FROM knowledge_items ki "
            "LEFT JOIN knowledge_categories kc ON kc.id = ki.category_id WHERE 1=1"
        )
        params: list[Any] = []
        if category_id is not None:
            sql += " AND ki.category_id = ?"
            params.append(category_id)
        sql += " ORDER BY kc.sort_order, ki.is_seed DESC, ki.updated_at DESC, ki.id DESC"
        return self._rows(sql, tuple(params))

    def get_knowledge_item(self, item_id: int) -> dict[str, Any] | None:
        return self._row(
            "SELECT ki.*, kc.name AS category_name FROM knowledge_items ki "
            "LEFT JOIN knowledge_categories kc ON kc.id = ki.category_id WHERE ki.id = ?",
            (item_id,),
        )

    def random_knowledge_item(self, category_id: int | None = None) -> dict[str, Any] | None:
        sql = (
            "SELECT ki.*, kc.name AS category_name FROM knowledge_items ki "
            "LEFT JOIN knowledge_categories kc ON kc.id = ki.category_id WHERE 1=1"
        )
        params: list[Any] = []
        if category_id is not None:
            sql += " AND ki.category_id = ?"
            params.append(category_id)
        sql += " ORDER BY RANDOM() LIMIT 1"
        return self._row(sql, tuple(params))

    def create_knowledge_item(
        self,
        category_id: int | None,
        title: str,
        summary: str,
        content: str,
        source_url: str = "",
    ) -> dict[str, Any]:
        item_id = self._write(
            "INSERT INTO knowledge_items(category_id, title, summary, content, source_url, is_seed) "
            "VALUES(?, ?, ?, ?, ?, 0)",
            (category_id, title, summary, content, source_url),
        )
        return self.get_knowledge_item(item_id)

    def update_knowledge_item(
        self,
        item_id: int,
        category_id: int | None,
        title: str,
        summary: str,
        content: str,
        source_url: str,
    ) -> dict[str, Any] | None:
        self._write(
            "UPDATE knowledge_items SET category_id = ?, title = ?, summary = ?, content = ?, "
            "source_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (category_id, title, summary, content, source_url, item_id),
        )
        return self.get_knowledge_item(item_id)

    def delete_knowledge_item(self, item_id: int) -> None:
        self._write("DELETE FROM knowledge_items WHERE id = ?", (item_id,))


db = Database()
