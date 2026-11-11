# RMMBench 操作类任务构建完整指南

> **快速核对：新建任务必须修改 4 个文件**
> 1. `configs/task_config.json` — 添加配置块（漏写会报 `KeyError: 'task'`）
> 2. `configs/__init__.py` — 添加 name2config 映射
> 3. `robocasa_task/新文件.py` — 编写 ConfigManager + Task（注意 `attach_objects` 要包含所有需要固定的物体）
> 4. `robocasa_task/__init__.py` — 添加 import

## 一、整体架构概览

RMMBench 任务系统的核心由三层构成：配置层、逻辑层、运行层。理解这三层的关系是构建任务的基础。

### 1.1 三层关系

```
配置层                    逻辑层                        运行层
┌──────────────────┐    ┌──────────────────────┐    ┌────────────────────┐
│ configs/         │    │ tasks/                │    │ dm_task.py          │
│   task_config.json│    │   config_manager.py   │    │   LM4ManipBaseTask  │
│   __init__.py    │    │   manipulation/        │    │   PrimitiveTask     │
│                  │───>│     navigation/        │───>│   (运行时实例化)     │
│  (声明物体/场景)   │    │       .py任务文件       │    │                     │
└──────────────────┘    └──────────────────────┘    └────────────────────┘
```

配置层声明"有什么"（物体、场景、容器），逻辑层定义"怎么放"（采样、定位、条件），运行层负责"怎么跑"（物理引擎、技能序列、初始化）。

### 1.2 涉及文件清单

| 文件 | 作用 | 何时修改 |
|------|------|---------|
| `RMMBench/configs/task_config.json` | 任务配置：声明物体、容器、场景、机器人位姿 | 新建任务时添加配置块 |
| `RMMBench/configs/__init__.py` | name2config 映射：文件名→任务名列表 | 新建任务时添加一行 |
| `RMMBench/tasks/config_manager.py` | BenchTaskConfigManager 基类（通用配置加载逻辑） | 仅在需要修改基类行为时 |
| `RMMBench/tasks/robocasa_task/新文件.py` | 具体任务的 ConfigManager + Task 实现 | 新建任务时创建 |
| `RMMBench/tasks/robocasa_task/__init__.py` | 模块导入注册 | 新建任务时添加一行 import |
| `RMMBench/utils/register.py` | 装饰器注册系统（add_config_manager / add_task） | 不需要修改 |
| `RMMBench/utils/skill_lib.py` | 技能库（pick / place / observe / end 等） | 不需要修改 |
| `RMMBench/tasks/condition.py` | 条件系统（is_grasped / contain_v / scene_contain 等） | 不需要修改，直接引用 |
| `RMMBench/utils/create_task/test_create_workspace_object_pos_orient.py` | 工作区计算、机器人位姿推算 | 仅在需要修改坐标计算时 |


## 二、命名体系：四个名称的对应关系

这是最容易出错的地方。一个任务涉及四个名称，它们之间存在严格的对应规则。

### 2.1 四个名称定义

| 名称 | 定义 | 举例（uncover_object 任务）                            |
|------|------|--------------------------------------------------|
| .py 文件名 | 物理文件名，去掉 .py 后缀 | `uncover_object`                                 |
| config key | task_config.json 中的键名 | `"uncover_object"`                               |
| name2config key | configs/__init__.py 中 name2config 的键 | `"uncover_object"`                               |
| register 任务名 | `@register.add_config_manager` / `@register.add_task` 装饰器参数 | `"uncover_fruit"或"uncover_apple"，这里和.py文件名不一定一致` |

### 2.2 对应规则

```
.py 文件名  ==  task_config.json 的 key  ==  name2config 的 key
register 装饰器名称  ==  name2config 的 value 列表中的元素
```

**关键：.py 文件名和 register 任务名可以不同。** 一个 .py 文件可以注册多个任务（value 列表有多个元素），也可以文件名和任务名完全相同。

### 2.3 三种典型场景

**场景 A：文件名与任务名相同**

以 `make_hamburger` 为例：

```python
# make_hamburger.py
@register.add_config_manager("make_hamburger")   # 任务名 == 文件名
class MakeHamburgerConfigManager(BenchTaskConfigManager): ...

@register.add_task("make_hamburger")              # 任务名 == 文件名
class MakeHamburgerTask(PrimitiveTask): ...
```

```python
# configs/__init__.py
"make_hamburger": ["make_hamburger"],            # key=文件名, value=[任务名]
```

```json
// task_config.json
"make_hamburger": { ... }                         // key = 文件名
```

```python
# robocasa_task/__init__.py
from ...make_hamburger import *                    # import 文件名
```

**场景 B：文件名与任务名不同**

以 `uncover_object` 为例：

```python
# uncover_object.py
@register.add_config_manager("uncover_fruit")     # 任务名 ≠ 文件名
class UncoverObjectConfigManager(BenchTaskConfigManager): ...

@register.add_task("uncover_fruit")               # 任务名 ≠ 文件名
class UncoverObjectTask(PrimitiveTask): ...
```

```python
# configs/__init__.py
"uncover_object": ["uncover_fruit"],              # key=文件名, value=[任务名]
```

```json
// task_config.json
"uncover_object": { ... }                         // key = 文件名
```

```python
# robocasa_task/__init__.py
from ...uncover_object import *                    // import 文件名
```

**场景 C：一个文件注册多个任务**

以 `wash_fruit.py` 为例：

```python
# wash_fruit.py
@register.add_config_manager("wash_fruit")          # 任务1
class WashFruitConfigManager(BenchTaskConfigManager): ...

@register.add_task("wash_fruit")                   # 任务1
class WashFruitTask(PrimitiveTask): ...

@register.add_config_manager("wash_fruit_semantic") # 任务2
class WashFruitSemanticConfigManager(WashFruitConfigManager): ...

@register.add_task("wash_fruit_semantic")           # 任务2
class WashFruitSemanticTask(WashFruitTask): ...
```

```python
# configs/__init__.py
"wash_fruit": ['wash_fruit', 'wash_fruit_semantic', 'wash_fruit_commonsense'],
```

### 2.4 名称如何被使用（运行时流程）

当用户传入 task_name 创建环境时（例如 `task_name="wash_fruit"`），系统执行以下流程：

```
用户传入 task_name="wash_fruit"
        │
        ▼
① register.load_config_manager("wash_fruit")
   → 从 register._config_managers 中取出 WashFruitConfigManager 类
        │
        ▼
② BenchTaskConfigManager.__init__ 中：
   find_key_by_value(name2config, "wash_fruit")
   → 在 name2config 中查找 "wash_fruit" 属于哪个 key 的 value
   → 找到 key = "wash_fruit"
        │
        ▼
③ configs.get("wash_fruit")
   → 从 task_config.json 中取出 "wash_fruit" 对应的配置块
        │
        ▼
④ 配置中的 asset 字段（seen_object, distractor, seen_container 等）
   被 setattr 到 self 上，供后续方法使用
```


## 三、task_config.json 配置详解

### 3.1 配置块结构

每个任务在 task_config.json 中对应一个顶层 key（= .py 文件名），结构如下：

```json
"文件名": {
    "robot": {
        "position": [x, y, z],
        "euler": [roll, pitch, yaw]
    },
    "task": {
        "asset": {
            "seen_object": ["apple_0", "bread_1"],
            "distractor": ["bell_pepper_0"],
            "seen_container": ["tray_5"],
            "mid_container": [{"pan_0": ["apple_0"]}],
            "random_scene": false,
            "robocasa_scene": "ONE_WALL_LARGE_2",
            "destination_position": "top",
            "fixture_surface": "island_counter_island_group"
        },
        "components": [],
        "scene": {"name": "empty"}
    }
}
```

### 3.2 字段含义详解

**robot 部分：**

| 字段 | 类型 | 说明 |
|------|------|------|
| position | [x, y, z] | 机器人在世界坐标系中的初始位置 |
| euler | [roll, pitch, yaw] | 机器人朝向（弧度）。常见值：`[0, 0, -1.57]`（朝Y负方向）、`[0, 0, 1.57]`（朝Y正方向）、`[0, 0, 0]`（朝X正方向） |

机器人位置参考值：wash_fruit 等大多数 island_counter 任务使用 `[2.15, -1.7, 0.0]`，euler `[0, 0, -1.57]`。stovetop 任务（如 select_steak）使用 `[3.2, -0.89, 0.0]`，euler `[0, 0, 1.57]`。

**机器人位置推导方法**：

`task_config.json` 中的 `robot.position` 不是手动估算的，而是通过 `get_work_info` 根据台面 workspace 和锚定方向自动计算得出的。推导步骤如下：

1. **查找 workspace**：从 `configs/robocasa_scenes_config/robocasa_scene_config.json` 中，根据 `robocasa_scene` 找到对应 `fixture_surface` 的 `workspace`，格式为 `[xmin, xmax, ymin, ymax, zmin, zmax]`。

2. **确定锚定方向**：`destination_position` 决定机器人站在工作区的哪一侧（top/bottom/left/right）。

3. **调用 `get_work_info`**：传入 workspace、`target_dim`、anchor=`destination_position`、`offset_dist`、`y_set`，返回的 `robot_xy` 字段即为机器人的 `[x, y]` 坐标。

4. **填入配置**：将 `robot_xy` 的 x、y 值填入 `robot.position`，z 固定为 `0.0`。

**快速获取方法**：在 `ConfigManager.get_object_info` 中打印 `self.work_info["robot_xy"]`，运行一次后即可得到精确的机器人位置，复制到 `task_config.json` 中。例如 `organize_snacks.py` 的机器人位置 `[3.2000671738525037, -3.800115813660509, 0.0]` 就是这样得到的。

**task.asset 部分：**

| 字段 | 类型 | 说明 |
|------|------|------|
| seen_object | list[str] | 目标物体池。`get_seen_task_config` 从中选取 target_entity |
| distractor | list[str] | 干扰物体池。纯字符串列表，会被放到 grid 采样点上 |
| seen_container | list[str] | 放置容器池。`get_seen_task_config` 从中选取 target_container |
| mid_container | list[dict] | 中间容器（可选）。格式 `[{"pan_0": ["apple_0"]}]`，pan_0 作为父物体，apple_0 作为子物体挂在 pan_0 的 subentities 下 |
| random_scene | bool | true 时从同场景类型中随机选一个变体（如 ONE_WALL_LARGE_{0,2,4,5}）；false 时固定使用 robocasa_scene 指定的场景 |
| robocasa_scene | str | 场景名。如 `ONE_WALL_LARGE_3`。如果末尾不带数字且 random_scene=false，系统会自动补 `_0` |
| destination_position | str | 机器人相对于工作区的锚定方向。从 `configs/robocasa_scenes_config/robocasa_scene_config.json` 中对应 fixture_surface 的 `destination_positions` 字段查找可用值。`around` 表示四个方向都可用；否则为 `top` / `bottom` / `left` / `right` 中的若干种。决定工作区裁切方向、物体朝向、机器人朝向 |
| fixture_surface | str | 工作台面名。从 `configs/robocasa_scenes_config/robocasa_scene_config.json` 中根据 `robocasa_scene` 查找对应 fixture 的 workspace。如 `island_counter_island_group`、`stovetop_main_group` |

**task.components：** 初始为空列表 `[]`，ConfigManager 在 `get_task_config` 流程中逐步向里追加场景配置、物体配置、容器配置等。

**task.scene：** 固定为 `{"name": "empty"}`，表示使用空场景（非 robocasa 内置场景布局），场景实体由 robocasa_scene 字段单独控制。

### 3.3 seen_object 的两种形态

**扁平列表（单组目标）：**

```json
"seen_object": ["apple_0", "bread_1", "steak_14"]
```

`get_seen_task_config` 默认行为是 `random.choice(self.seen_object)` 选一个作为 target_entity。

**嵌套列表（多组目标，用于 Classify 任务）：**

```json
"seen_object": [["apple_0", "orange_0"], ["carrot_0", "corn_0"]]
```

ClassifyConfigManager 会从每组中各选一个，target_entity 变为 `["apple_0", "carrot_0"]`。

### 3.4 全部目标都选中的覆写方式

当需要让 seen_object 中的所有物体都作为 target_entity 时（不做 random.choice），在 ConfigManager 子类中覆写 `get_seen_task_config`：

```python
def get_seen_task_config(self):
    target_entity = self.seen_object          # 全选，不做 random.choice
    container = random.choice(self.seen_container) if self.seen_container else None
    return self.get_task_config(target_entity=target_entity,
                                target_container=container,
                                init_container=None,
                                **self.kwargs)
```


## 四、ConfigManager 类详解

ConfigManager 负责从配置生成完整的 task config。基类 `BenchTaskConfigManager` 在 `tasks/config_manager.py` 中定义，子类在各自的 .py 文件中覆写方法。

### 4.1 __init__ 做了什么

当 `register.load_config_manager(task_name)(task_name)` 被调用时，执行链如下：

```
__init__(task_name, num_objects, **kwargs)
│
├── 1. 从 task_config.json 加载配置
│      find_key_by_value(name2config, task_name) → 找到 config key
│      configs.get(config_key) → 取出配置块
│      self.config.update(配置块)
│
├── 2. 解析 asset 字段，setattr 到 self
│      遍历 attr 列表：random_scene, destination_position, fixture_surface,
│      robocasa_scene, mid_contain, mid_container, class_1, class_2,
│      distractor, seen_object, unseen_object, seen_container,
│      unseen_container, seen_init_container, unseen_init_container
│      → self.seen_object, self.distractor, self.seen_container 等
│
├── 3. distractor / unseen_object 互通
│      如果 distractor 为 None 但 unseen_object 有值 → 互通
│      如果 unseen_object 为 None 但 distractor 有值 → 互通
│
├── 4. 解析 mid_container
│      [{"pan_0": ["apple"]}] → self.mid_container_mapping = {"pan_0": ["apple"]}
│
├── 5. 计算 all_entities
│      flatten_list(seen_object) + flatten_list(distractor) + flatten_list(seen_container)
│      如果有 mid_container_mapping，追加 parent 名称
│      → self.all_entities = ["apple", "peach", "tray", "pan_0"]
│
└── 6. num_object 随机选取
       如果 num_objects 是列表 → random.choice
       如果是 int → 直接使用
```

### 4.2 get_seen_task_config — 目标选择

基类默认实现：

```python
def get_seen_task_config(self):
    target_entity = random.choice(self.seen_object)    # 从池中随机选一个
    container = random.choice(self.seen_container)      # 从池中随机选一个容器
    init_container = random.choice(self.seen_init_container)  # 如有
    return self.get_task_config(target_entity=target_entity,
                                target_container=container,
                                init_container=init_container,
                                mid_contain=self.mid_contain,
                                **self.kwargs)
```

覆写场景：当所有 seen_object 都是目标时，把 `random.choice(self.seen_object)` 改为 `self.seen_object`。

### 4.3 get_task_config — 核心流程（顺序固定）

这是最关键的方法，定义了配置生成的执行顺序。基类实现：

```python
def get_task_config(self, target_entity, target_container, init_container, mid_contain=None, **kwargs):
    self.target_entity = target_entity
    self.target_container = target_container
    self.init_container = init_container
    
    self.get_object_info()           # ① 计算工作区、采样点
    self.load_robocasa_scene()       # ② 加载场景实体
    self.load_containers(...)        # ③ 放置容器（target_container）
    self.load_init_containers(...)   # ④ 放置初始容器（如有）
    self.load_mid_contain(...)       # ⑤ 放置中间容器（旧版 mid_contain 格式）
    self.load_objects(...)           # ⑥ 放置物体（target_entity + distractor）
    self.get_condition_config(...)   # ⑦ 生成成功条件
    self.get_instruction(...)        # ⑧ 生成指令文本
    self.get_camera_config()         # ⑨ 设置相机
    return self.config
```

每一步都会向 `self.config["task"]["components"]` 中追加实体配置。

### 4.4 get_object_info — 工作区与采样

```python
def get_object_info(self, workregion_offset=-0.65, workregion_y_set=0.1,
                    target_dim=(0.3, 0.25), grid_size=[6, 6]):
    super().get_object_info(workregion_offset, workregion_y_set,
                            target_dim=target_dim, grid_size=grid_size)
```

基类逻辑：
1. 从 `robocasa_scenes_config/robocasa_scene_config.json` 读取场景的 fixture_surface workspace
2. 调用 `get_work_info(workspace, target_dim, anchor=destination_position, offset_dist, y_set)` 计算工作区区域、z 高度、物体朝向、机器人位姿
3. 计算 n_samples（采样点数量）：

```
n_samples = len(target_entity) + len(distractor) + len(mid_parents) - len(mid_children)
```

mid_container 的 parent 占一个采样点，child 不占（作为 subentity 挂在 parent 下）。

4. 调用 `grid_sample(workregion, grid_size, n_samples)` 随机采样 n_samples 个点

子类通常只覆写参数（workregion_offset, workregion_y_set, target_dim, grid_size），不改变核心逻辑。

### 4.5 load_containers — 容器放置

基类默认实现根据 workregion 计算容器位置：

```python
def load_containers(self, target_container, offset=0.3, y_set=0.1, direction="left"):
    if target_container is not None:
        if self.work_info and self.target_container:
            container_info = self.get_container_info_from_workregion(
                self.work_info,
                anchor=self.destination_position,
                offset=offset,
                y_set=y_set,
                direction=direction
            )
            container_config = self.get_entity_config(
                target_container,
                position=container_info["position"],
                orientation=container_info["orientation"]
            )
            self.config["task"]["components"].append(container_config)
```

参数含义：
- offset：容器距工作区边缘的距离（米）
- y_set：容器在工作区长度方向上的偏移
- direction：容器放在工作区的哪一侧（"left" / "right"）

子类常见覆写：调整 offset / y_set / direction 参数，或在 z 上加偏置。

### 4.6 load_objects — 物体放置

基类实现（有 mid_container 时自动处理 parent-child 关系）：

```python
def load_objects(self, target_entity):
    if self.work_info:
        orientation = self.work_info["object_orientation"]
        all_objects = flatten_list(self.target_entity) + flatten_list(self.distractor)
        
        # 1. 区分 regular_objects 和 mid_children
        mid_children = set()
        for children in self.mid_container_mapping.values():
            mid_children.update(children)
        regular_objects = [obj for obj in all_objects if obj not in mid_children]
        self.objects = regular_objects + list(self.mid_container_mapping.keys())
        
        # 2. 在采样点上放置 regular_objects
        z = self.work_info["z"]
        points_3d = [[x, y, z] for x, y in self.sampled_points]
        for obj in regular_objects:
            config = self.get_entity_config(obj, position=points_3d[point_idx], orientation=orientation)
            self.config["task"]["components"].append(config)
            point_idx += 1
        
        # 3. 在采样点上放置 mid_container parents，children 作为 subentities
        for parent, children in self.mid_container_mapping.items():
            parent_config = self.get_entity_config(parent, position=points_3d[point_idx], orientation=orientation)
            parent_config["subentities"] = []
            for j, child in enumerate(children):
                child_config = self.get_entity_config(child,
                    position=[j*0.1 - 0.05*(len(children)-1), 0, -0.05],
                    orientation=[0, 0, 0])
                parent_config["subentities"].append(child_config)
            self.config["task"]["components"].append(parent_config)
            point_idx += 1
    else:
        # 无 work_info 的 fallback：简单线性排列
        ...
```

子类常见覆写场景：
- 调用 `super().load_objects(target_entity)` 后对特定物体做后处理（如翻转 pan）
- 完全自定义布局（硬编码位置，如 test_texture）

### 4.7 get_condition_config — 成功条件（必须覆写）

基类中是 `raise NotImplementedError`，子类必须实现。可用条件类型：

| 条件名 | 参数 | 用途 |
|--------|------|------|
| `contain_v` | container, entities, vel_th | 物体在容器内且静止 |
| `scene_contain` | scene, container_name, entities, vel_th | 物体在场景固定容器内（如 sink） |
| `scene_not_contain` | scene, container_name, entities, vel_th | 物体不在场景容器内 |
| `is_grasped` | entities, robot | 物体被机器人抓住 |
| `on` | entities, target_entity | 物体在目标物体上方 |
| `above` | entities, target_entity, distance | 物体在目标上方一定距离内 |
| `lift` | entities, target_height | 物体被举到指定高度 |
| `or` | list[dict] | 满足任一条件（如聚类任务的两种放法） |

写法示例：

```python
# 单条件
def get_condition_config(self, target_entity, target_container, **kwargs):
    conditions_config = dict(
        is_grasped=dict(
            entities=target_entity,     # 直接传 list，init_conditions 会自动查 entities
            robot="franka"
        )
    )
    self.config["task"]["conditions"] = conditions_config

# 双条件（同时满足）
def get_condition_config(self, target_entity, target_container, **kwargs):
    conditions_config = dict(
        scene_contain=dict(
            scene=self.robocasa_scene,
            container_name="sink_island_group",
            entities=[self.target_entity],
            vel_th=0.01,
        ),
        scene_not_contain=dict(
            scene=self.robocasa_scene,
            container_name="sink_island_group",
            entities=self.distractor,
            vel_th=0.01,
        )
    )
    self.config["task"]["conditions"] = conditions_config
```

### 4.8 get_instruction — 指令文本

生成自然语言指令：

```python
def get_instruction(self, target_entity, target_container, **kwargs):
    instruction = [f"Put the {self.extract_base_name(target_entity)} into the pan."]
    self.config["task"]["instructions"] = instruction
    return self.config
```

`extract_base_name` 会去掉物体名末尾的 `_数字` 后缀，如 `apple_0` → `apple`。

### 4.9 mid_container 机制详解

task_config.json 中声明：

```json
"mid_container": [{"pan_0": ["apple_0"]}]
```

处理流程：

```
__init__ 解析:
  [{"pan_0": ["apple_0"]}] → self.mid_container_mapping = {"pan_0": ["apple_0"]}

all_entities 追加:
  原: ["apple_0", "peach", "tray"]
  后: ["apple_0", "peach", "tray", "pan_0"]

n_samples 计算:
  len(target_entity) + len(distractor) + len(parents) - len(children)
  = 1 + 1 + 1 - 1 = 2

load_objects 中:
  regular_objects = ["peach"]           (apple_0 被排除，因为是 mid_child)
  self.objects = ["peach", "pan_0"]
  
  peach → 放在采样点 0
  pan_0 → 放在采样点 1
    └─ subentities: [apple_0] (position=[0, 0, -0.05], 即 pan 下方)

load_objects 后处理（子类）:
  pan 的 orientation = [o[0], o[1]+3.14, o[2]]  (翻转盖住下方物体)
```


## 五、Task 类详解

Task 类继承 `PrimitiveTask`（→ `LM4ManipBaseTask` → `composer.Task`），负责运行时行为。

### 5.1 类结构

```python
@register.add_task("make_hamburger")
class MakeHamburgerTask(PrimitiveTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["plate", "bread", "steak"]   # 需要 attach 到 arena 的物体
        super().__init__(task_name, robot=robot, **kwargs)
    
    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)   # 执行基类构建流程
        self.reset_entities_positions()             # 高度自适应
        self.attach_entities_to_arena()             # 固定容器到台面
    
    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)
        for key, entity in self.entities.items():
            self.settle_object(key, entity, physics)  # 物理稳定
    
    def reset_entities_positions(self):
        ...  # 根据物体高度调整 z
    
    def attach_entities_to_arena(self):
        ...  # 将容器固定到台面
    
    def get_expert_skill_sequence(self, physics):
        ...  # 专家技能序列
```

### 5.2 attach_objects

列表中的字符串用于模糊匹配 entity 名称。如果 entity 名中包含这些字符串，就会被 detach 并 attach 到 arena（固定在世界中）。常见的需要 attach 的物体：pan、tray、plate、bread（面包片较薄，容易滑动）等。

基类 `dm_task.py` 的 `attach_entities_to_arena` 已有实现：对有内部关节的物体（如 stovetop 的 knob）用 equality 约束，对无关节的物体直接 detach+attach。

### 5.3 reset_entities_positions — 高度自适应

物体从 work_info 获取的 z 是台面高度，但不同物体有不同的高度（如 pan 比 apple 高）。这个方法通过 `entity.get_placement_height()` 获取物体高度，加到 init_pos[2] 上：

```python
def reset_entities_positions(self):
    if self.config_manager.all_entities is not None:
        entities = self.config_manager.all_entities
        for k in entities:
            entity = self.entities.get(k)
            if entity is None:
                continue
            height = entity.get_placement_height()
            entity.init_pos[2] += height
```

变体：如果某些物体不需要高度调整（如被 pan 盖住的目标），可以跳过：

```python
if self.config_manager.target_entity in k:
    continue
```

### 5.4 get_expert_skill_sequence — 专家技能序列

定义机器人执行任务的技能序列，返回一个 `partial` 列表。可用的 SkillLib 方法：

| 方法 | 参数 | 用途 |
|------|------|------|
| `SkillLib.pick` | target_entity_name / target_pos | 抓取物体 |
| `SkillLib.place` | target_container_name / target_pos / bbox | 放置物体 |
| `SkillLib.observe` | motion_planning_kwargs | 观察环境（等待物理稳定） |
| `SkillLib.end` | wait_time, gripper_state | 结束任务 |

典型模式：

```python
# 单目标：pick → place → end
def get_expert_skill_sequence(self, physics):
    target_entity = self.config_manager.target_entity
    skill_sequence = [
        partial(SkillLib.pick, target_entity_name=target_entity),
        partial(SkillLib.place, target_container_name=self.target_container),
        partial(SkillLib.end),
    ]
    return skill_sequence

# 多目标循环：pick → place → observe × N → end
def get_expert_skill_sequence(self, physics):
    target_entities = self.config_manager.target_entity
    skill_sequence = []
    for entity in target_entities:
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=entity),
            partial(SkillLib.place, target_container_name=self.target_container),
            partial(SkillLib.observe),
        ])
    skill_sequence.extend([partial(SkillLib.end)])
    skill_sequence = self.remove_second_last(skill_sequence)  # 去掉最后一个 observe
    return skill_sequence

# 中间容器遮挡：pick pan → place tray → observe → pick target → place sink → end
def get_expert_skill_sequence(self, physics):
    target_entity = self.config_manager.target_entity
    mid_container_name = list(self.config_manager.mid_container_mapping.keys())[0]
    sink_placement = [2.74, -2.2, 0.94]
    skill_sequence = [
        partial(SkillLib.pick, target_entity_name=mid_container_name),
        partial(SkillLib.place, target_container_name=self.target_container),
        partial(SkillLib.observe),
        partial(SkillLib.pick, target_entity_name=target_entity),
        partial(SkillLib.place, target_pos=sink_placement),
        partial(SkillLib.end),
    ]
    return skill_sequence
```

`remove_second_last` 方法（基类提供）：去掉列表倒数第二个元素，常用于去掉最后一个循环中的多余 observe。

### 5.5 settle_object

在 `initialize_episode` 中对每个 entity 调用，让物理引擎跑几步使物体自然落到台面上，避免初始穿模。基类 `dm_task.py` 中有实现，但某些物体名（如 `ONE_WALL_LARGE`）会被跳过。


## 六、destination_position 与工作区计算

### 6.1 四个锚定方向

`destination_position` 决定了机器人相对于工作台的位置，进而影响工作区裁切和物体朝向。

| 方向 | 机器人位置 | robot_orientation | object_orientation | workregion 裁切方式 |
|------|-----------|-------------------|--------------------|--------------------|
| bottom | Y 轴小端 | [0, 0, 1.57] | [0, 0, 0] | 从 y_min 向上裁切 |
| top | Y 轴大端 | [0, 0, -1.57] | [0, 0, 3.14] | 从 y_max 向下裁切 |
| left | X 轴小端 | [0, 0, 0] | [0, 0, -1.57] | 从 x_min 向右裁切 |
| right | X 轴大端 | [0, 0, 3.14] | [0, 0, 1.57] | 从 x_max 向左裁切 |

### 6.2 get_work_info 返回值

```python
{
    "workregion": [xmin, xmax, ymin, ymax, zmin, zmax],  # 裁切后的工作区
    "z": z_max,                                          # 台面高度
    "robot_orientation": [0, 0, 1.57],                   # 机器人朝向
    "object_orientation": [0, 0, 0],                     # 物体朝向
    "anchor": "bottom",                                   # 锚定方向
    "robot_xy": [x, y]                                    # 机器人 XY 位置
}
```

### 6.3 get_container_info_from_workregion

根据工作区边缘和锚定方向，计算容器在台面上的位置：

```python
container_info = self.get_container_info_from_workregion(
    self.work_info,
    anchor=self.destination_position,  # "top" / "bottom" / "left" / "right"
    offset=0.3,       # 距工作区边缘的距离
    y_set=0.1,        # 沿边缘方向的偏移
    direction="left"  # 容器放在工作区的左侧还是右侧
)
# 返回: {"position": [x, y, z], "orientation": [roll, pitch, yaw]}
```


## 七、条件系统详解

### 7.1 条件的运行时加载

在 `dm_task.py` 的 `init_conditions` 中，遍历 `conditions_config` 的每个 key-value：

```python
for condition_key, specific_condition in condition_config.items():
    condition_cls = register.load_condition(condition_key)  # 如 "is_grasped" → IsGraspedCondition
    for k, entities in specific_condition.items():
        if k == "robot":
            specific_condition[k] = self.robot               # 替换为 robot 实例
        if isinstance(entities, str):
            specific_condition[k] = self.entities.get(entities, None)  # 字符串→entity实例
        if isinstance(entities, list):
            specific_condition[k] = [self.entities.get(e, None) for e in entities]  # 列表逐个替换
    condition = condition_cls(**specific_condition)
    conditions.append(condition)
self.conditions = ConditionSet(conditions)
```

**关键**：condition_config 中的 entities 字段，无论是字符串还是列表，都会被自动替换为实际的 entity 对象。所以可以直接传 `target_entity`（字符串或列表）。

### 7.2 常用条件写法参考

```python
# contain_v: 物体在容器内
dict(contain_v=dict(container=target_container, entities=[target_entity], vel_th=0.01))

# scene_contain: 物体在场景固定容器内（如水槽）
dict(scene_contain=dict(scene=self.robocasa_scene, container_name="sink_island_group",
     entities=[self.target_entity], vel_th=0.01))

# is_grasped: 物体被抓住
dict(is_grasped=dict(entities=target_entity, robot="franka"))

# or: 满足任一
dict(or=[
    dict(contain_1=dict(entities=cls1, container="tray_0_0")),
    dict(contain_2=dict(entities=cls2, container="tray_1_1"))
])
```


## 八、完整构建流程（六步法）

### 第一步：明确任务要素

根据需求确定：

- 目标物体（seen_object）：哪些物体是操作对象
- 干扰物（distractor）：哪些是干扰，可选
- 容器（seen_container）：放到哪里
- 中间容器（mid_container）：是否有遮挡/包含关系，可选
- 场景（robocasa_scene）：用哪个厨房场景
- 台面（fixture_surface）：在哪个台面上操作
- 朝向（destination_position）：机器人在台面的哪一侧

### 第二步：task_config.json 添加配置块

文件：`RMMBench/configs/task_config.json`

在 JSON 末尾添加，key = .py 文件名：

```json
"文件名": {
    "robot": {
        "position": [2.15, -1.7, 0.0],
        "euler": [0, 0, -1.57]
    },
    "task": {
        "asset": {
            "seen_object": ["bread_1", "bread_2", "steak_14"],
            "seen_container": ["plate_1"],
            "random_scene": false,
            "robocasa_scene": "ONE_WALL_LARGE_3",
            "destination_position": "left",
            "fixture_surface": "island_counter_island_group"
        },
        "components": [],
        "scene": {"name": "empty"}
    }
}
```

### 第三步：configs/__init__.py 添加映射

文件：`RMMBench/configs/__init__.py`

在 name2config 字典中添加，key = .py 文件名，value = [任务名]：

```python
"文件名": ["任务名"],
```

### 第四步：编写 .py 任务文件

目录：`RMMBench/tasks/robocasa_task/`

文件名 = task_config.json 的 key。文件内包含两个类：

```python
import random
from functools import partial
from RMMBench.tasks.primitive.base import PrimitiveTask
from RMMBench.tasks.config_manager import BenchTaskConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib


@register.add_config_manager("任务名")
class XxxConfigManager(BenchTaskConfigManager):
    def __init__(self, task_name, num_objects=[1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)

    # [可选] 覆写目标选择逻辑
    def get_seen_task_config(self):
        ...

    # [可选] 覆写工作区参数
    def get_object_info(self, workregion_offset=-0.65, workregion_y_set=0.1,
                        target_dim=(0.3, 0.25), grid_size=[6, 6]):
        super().get_object_info(workregion_offset, workregion_y_set,
                               target_dim=target_dim, grid_size=grid_size)

    # [可选] 覆写容器放置参数
    def load_containers(self, target_container, offset=0.25, y_set=0.09, direction="left"):
        ...

    # [可选] 覆写物体放置逻辑
    def load_objects(self, target_entity):
        ...

    # [必须] 定义成功条件
    def get_condition_config(self, target_entity, target_container, **kwargs):
        ...

    # [必须] 定义指令文本
    def get_instruction(self, target_entity, target_container, **kwargs):
        ...


@register.add_task("任务名")
class XxxTask(PrimitiveTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["关键词1", "关键词2"]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        super().build_from_config(eval, **kwargs)
        self.reset_entities_positions()
        self.attach_entities_to_arena()

    def initialize_episode(self, physics, random_state):
        super().initialize_episode(physics, random_state)
        for key, entity in self.entities.items():
            self.settle_object(key, entity, physics)

    def reset_entities_positions(self):
        ...

    def attach_entities_to_arena(self):
        ...

    def get_expert_skill_sequence(self, physics):
        ...
```

### 第五步：robocasa_task/__init__.py 添加导入

文件：`RMMBench/tasks/robocasa_task/__init__.py`

```python
from RMMBench.tasks.robocasa_task.文件名 import *
```

### 第六步：验证一致性

确认以下四处名称对应正确：

```
task_config.json 的 key       ==  .py 文件名（不含 .py）
configs/__init__.py 的 key    ==  .py 文件名
configs/__init__.py 的 value  ==  register 装饰器参数
robocasa_task/__init__.py     ==  from ...文件名 import *
```


## 九、参考模板

| 场景类型 | 参考文件 | 特点 |
|---------|---------|------|
| 单目标 + 水槽 | `wash_fruit.py` | scene_contain 条件，pick→place→observe 循环 |
| 单目标 + 容器放置 | `ONE_WALL_LARGE.py` | contain_v 条件，pick→place→end |
| 全部目标选中 | `make_hamburger.py` | get_seen_task_config 覆写，is_grasped 条件 |
| mid_container 遮挡 | `uncover_object.py` | pan 翻转，先移开容器再操作目标 |
| 硬编码布局 | `test_texture.py` | 无 work_info，手动指定位置 |
| 多组分类 | `wash_fruit_tidy_table.py` | ClassifyConfigManager，嵌套 seen_object |
| 多任务同文件 | `wash_fruit.py` | wash_fruit + wash_fruit_semantic + wash_fruit_commonsense |
| 复合导航任务 | `composite_organize_snacks.py` | CompositeNavigationTask，多区域 + 导航条件，详见 `/Users/lh/work/RMMBench/RMMBench/tasks/task_auto/composite_task.md` |


## 十、常见错误与注意事项

1. **文件名 vs 任务名混淆**：task_config.json 的 key 是 .py 文件名，不是 register 装饰器参数。一个文件可以注册多个不同名称的任务。

2. **self.distractions 是死代码**：基类中 `self.distractions = []` 始终为空列表，不要在 n_samples 或 load_objects 中使用它。干扰物应该用 `self.distractor`。

3. **target_entity vs seen_object**：seen_object 是完整物体池，target_entity 是从中选出的子集。不要用 seen_object 替代 target_entity 参与采样计算。

4. **pan 翻转方向**：应叠加到原有 orientation 上 `[o[0], o[1]+3.14, o[2]]`，而不是直接替换为 `[0, 3.14, 0]`，否则 pan 的 xy 朝向会不正确。

5. **mid_child 的 z 偏置**：子物体在父物体下方，z 应为负值（如 -0.05），不是正值。

6. **专家序列为扁平列表**：不要用 if 分支，直接写成一长串 partial 列表。

7. **get_condition_config 必须实现**：基类中是 `raise NotImplementedError`，不实现会报错。

8. **import random**：如果 get_seen_task_config 中用到了 `random.choice`，需要在文件顶部 `import random`。

9. **all_entities 与 reset_entities_positions**：如果添加了 mid_container，需要确保 parent 也加入 all_entities，否则 reset_entities_positions 不会调整 parent 的高度。

10. **condition 中 entities 参数**：condition_config 中的 entities 字段会被 init_conditions 自动替换为 entity 实例。传字符串名（如 "apple_0"）或列表（如 ["apple_0", "bread_1"]）均可，系统会自动查 self.entities 字典。


## 十一、典型场景参数参考

以下按场景/台面/锚定方向分类，提供可直接复用的参数组合。

### 11.1 island_island_group + bottom

**参考任务**：`organize_snacks.py`（`select_snacks_to_tray`）

**场景配置**（直接复制自 `organize_snacks.py` 的 `task_config.json`）：
- `robocasa_scene`: `U_SHAPED_LARGE_6`
- `fixture_surface`: `island_island_group`
- `destination_position`: `bottom`
- `robot.position`: `[3.2000671738525037, -3.800115813660509, 0.0]`
- `robot.euler`: `[0, 0, 1.57]`

**ConfigManager 参数**（直接复制自 `organize_snacks.py`）：

```python
def get_object_info(self, workregion_offset=0, workregion_y_set=0.1,
                    target_dim=(0.4, 0.4), grid_size=[8, 8]):
    super().get_object_info(workregion_offset, workregion_y_set,
                            target_dim=target_dim, grid_size=grid_size)

def load_containers(self, target_container, offset=0.25, y_set=0.09, direction="left"):
    if target_container is not None:
        if self.work_info and self.target_container:
            container_info = self.get_container_info_from_workregion(
                self.work_info,
                anchor=self.destination_position,
                offset=offset,
                y_set=y_set,
                direction=direction
            )
            container_config = self.get_entity_config(
                target_container,
                position=container_info["position"],
                orientation=container_info["orientation"]
            )
            self.config["task"]["components"].append(container_config)
```

**Task 参数**（直接复制自 `organize_snacks.py`）：

```python
def __init__(self, task_name, robot, **kwargs):
    self.attach_objects = ["tray", "sink"]
    super().__init__(task_name, robot=robot, **kwargs)
```

**参数说明**：
- `workregion_offset=0`：工作区在 x 方向不额外偏移，保持居中
- `workregion_y_set=0.1`：工作区向远离机器人方向（y 正方向）偏移 0.1m
- `target_dim=(0.4, 0.4)`：工作区裁切为 0.4m × 0.4m
- `grid_size=[8, 8]`：8×8 网格采样
- `load_containers(offset=0.25, y_set=0.09, direction="left")`：容器放在工作区左侧，距边缘 0.25m，沿边缘偏移 0.09m
- `attach_objects = ["tray", "sink"]`：将 tray 和 sink 固定到场景中
