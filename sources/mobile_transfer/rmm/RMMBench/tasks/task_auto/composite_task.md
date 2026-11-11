# RMMBench 复合导航类任务构建指南

> **快速核对：新建任务必须修改 4 个文件**
> 1. `configs/task_config.json` — 添加 `composite_configs` 配置块（漏写会报 `KeyError: 'task'`）
> 2. `configs/__init__.py` — 添加 name2config 映射
> 3. `robocasa_task/新文件.py` — 编写 ConfigManager + Task（注意 `attach_objects` 要包含所有需要固定的物体）
> 4. `robocasa_task/__init__.py` — 添加 import

## 一、与单区域任务的核心区别

| 维度 | 单区域任务（PrimitiveTask） | 复合导航任务（CompositeNavigationTask） |
|------|---------------------------|--------------------------------------|
| 基类 | `BenchTaskConfigManager` + `PrimitiveTask` | `CompositeNavigationConfigManager` + `CompositeNavigationTask` |
| 配置字段 | `task.asset.seen_object` / `seen_container` | `task.asset.composite_configs`（数组） |
| 区域数量 | 1 个 fixture_surface | 多个 fixture_surface |
| 工作区 | 单个 `work_info` | `work_info` 数组，按 layout 索引 |
| 采样点 | 单个 `sampled_points` | `sampled_points` 数组，按 layout 索引 |
| 目标物体 | `self.target_entity` 扁平列表 | `self.merged_seen_object` 嵌套列表 |
| 目标容器 | `self.target_container` 字符串 | `self.merged_seen_container` 嵌套列表 |
| 条件系统 | `is_grasped` / `contain_v` / `scene_contain` | `asyn_sequence` + `ordered_indices` |
| 机器人 | 固定机械臂（franka） | 移动底盘（pandaomron） |


## 二、涉及文件清单

| 文件 | 作用 | 何时修改 |
|------|------|---------|
| `RMMBench/configs/task_config.json` | 添加 `composite_configs` 配置块 | 新建任务时 |
| `RMMBench/configs/__init__.py` | name2config 映射 | 新建任务时添加一行 |
| `RMMBench/tasks/robocasa_task/新文件.py` | `CompositeNavigationConfigManager` + `CompositeNavigationTask` | 新建任务时创建 |
| `RMMBench/tasks/robocasa_task/__init__.py` | 模块导入注册 | 新建任务时添加一行 import |
| `RMMBench/tasks/config_manager.py` | `CompositeNavigationConfigManager` 基类 | 不需要修改 |
| `RMMBench/tasks/robocasa_task/base.py` | `CompositeNavigationTask` 基类 | 不需要修改 |


## 三、命名体系

命名规则与单区域任务一致：

```
.py 文件名  ==  task_config.json 的 key  ==  name2config 的 key
register 装饰器名称  ==  name2config 的 value 列表中的元素
```


## 四、task_config.json 配置详解

### 4.1 配置块结构

```json
"文件名": {
    "robot": {
        "position": [x, y, z],
        "euler": [roll, pitch, yaw]
    },
    "task": {
        "asset": {
            "composite_configs": [
                {
                    "seen_object": ["apple_0"],
                    "distractor": ["bread_1"],
                    "mid_container": [{"pan_0": ["apple_0"]}],
                    "fixture_surface": "counter_main_main_group",
                    "destination_position": "bottom"
                },
                {
                    "seen_container": ["plate_1"],
                    "distractor": ["bread_2"],
                    "fixture_surface": "island_island_group",
                    "destination_position": "top"
                }
            ],
            "robocasa_scene": "WRAPAROUND_9"
        },
        "components": [],
        "scene": {"name": "empty"}
    }
}
```

### 4.2 composite_configs 数组

每个元素是一个独立区域的配置，支持字段与单区域 `task.asset` 相同：

| 字段 | 说明 |
|------|------|
| `seen_object` | 目标物体池（该区域内） |
| `distractor` | 干扰物体池（该区域内） |
| `seen_container` | 放置容器池（该区域内） |
| `mid_container` | 中间容器（该区域内） |
| `fixture_surface` | 该区域的台面名。从 `configs/robocasa_scenes_config/robocasa_scene_config.json` 中根据 `robocasa_scene` 查找对应 fixture 的 workspace |
| `destination_position` | 机器人相对于该区域的锚定方向。从 `robocasa_scene_config.json` 中对应 fixture_surface 的 `destination_positions` 字段查找可用值。`around` 表示四个方向都可用；否则为 `top` / `bottom` / `left` / `right` 中的若干种 |

**注意**：`robocasa_scene` 放在 `composite_configs` 外层，所有区域共享同一个场景。`fixture_surface` 和 `destination_position` 的组合必须在 `robocasa_scene_config.json` 中有定义，否则工作区计算会失败。


## 五、ConfigManager 类详解

### 5.1 继承与初始化

```python
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager

@register.add_config_manager("任务名")
class XxxConfigManager(CompositeNavigationConfigManager):
    def __init__(self, task_name, num_objects=[3, 1], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [...]
        self.CONTAINER_CONFIG_TABLE = [...]
```

- `num_objects` 是数组，长度等于 `composite_configs` 的数量
- `LAYOUT_CONFIG_TABLE`：每个 layout 的 `get_object_info` 参数
- `CONTAINER_CONFIG_TABLE`：每个 layout 的 `load_containers` 参数

### 5.2 LAYOUT_CONFIG_TABLE

为每个区域指定工作区裁切和采样参数：

```python
self.LAYOUT_CONFIG_TABLE = [
    {
        "workregion_offset": 0,
        "workregion_y_set": 0.1,
        "target_dim": (0.4, 0.4),
        "grid_size": [8, 8]
    },
    {
        "workregion_offset": 0,
        "workregion_y_set": 0.02,
        "target_dim": (0.4, 0.4),
        "grid_size": [6, 6]
    }
]
```

### 5.3 CONTAINER_CONFIG_TABLE

为每个区域指定容器放置参数：

```python
self.CONTAINER_CONFIG_TABLE = [
    {},  # Layout 0: no container
    {
        "configs": [
            {"offset": 0.25, "y_set": 0.09, "direction": "left", "z_set": 0}
        ]
    }
]
```

- `configs` 数组长度应与该 layout 的 `seen_container` 数量一致
- 每个 config 支持：`offset`, `y_set`, `direction`, `z_set`

### 5.4 get_condition_config — 复合条件系统

使用 `asyn_sequence` 定义多步骤条件：

```python
def get_condition_config(self, **kwargs):
    conditions_config = dict()
    conditions_config["asyn_sequence"] = [
        # Step 0: 导航到区域 0
        dict(
            contain_robot_pose=dict(
                target_bbox=self.target_bbox[0],
                robot="pandaomron"
            ),
            robot_orientation=dict(
                target_orientation="top",
                target_bbox=self.target_bbox[0],
                robot="pandaomron"
            )
        ),
        # Step 1: 导航到区域 1
        dict(
            contain_robot_pose=dict(
                target_bbox=self.target_bbox[1],
                robot="pandaomron"
            ),
            robot_orientation=dict(
                target_orientation="top",
                target_bbox=self.target_bbox[1],
                robot="pandaomron"
            )
        ),
        # Step 2: 操作完成条件
        dict(
            contain=dict(
                entities=[self.merged_seen_object[0][0]],
                container=f"{self.merged_seen_container[1][0]}",
            )
        ),
    ]
    conditions_config["ordered_indices"] = [0, 1]

    self.target_object_info[0]["target_bbox"] = self.target_bbox[0]
    self.target_object_info[0]["target_orientation"] = "top"
    self.target_object_info[1]["target_bbox"] = self.target_bbox[1]
    self.target_object_info[1]["target_orientation"] = "top"

    self.config["task"]["conditions"] = conditions_config
```

| 条件类型 | 用途 |
|---------|------|
| `contain_robot_pose` | 机器人进入目标区域的 bbox |
| `robot_orientation` | 机器人在目标区域的朝向正确 |
| `contain` | 物体在容器内 |
| `ordered_indices` | 指定哪些步骤必须按顺序完成 |

### 5.5 数据访问方式

| 数据 | 单区域任务 | 复合导航任务 |
|------|-----------|-------------|
| 目标物体 | `self.target_entity` | `self.merged_seen_object[idx][i]` |
| 目标容器 | `self.target_container` | `self.merged_seen_container[idx][i]` |
| work_info | `self.work_info` | `self.work_info[idx]` |
| 采样点 | `self.sampled_points` | `self.sampled_points[idx]` |
| 所有实体 | `self.all_entities` | `self.composite_entities` |


## 六、Task 类详解

### 6.1 继承与初始化

```python
from RMMBench.tasks.robocasa_task.base import CompositeNavigationTask

@register.add_task("任务名")
class XxxTask(CompositeNavigationTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = ["tray", "pan"]
        super().__init__(task_name, robot=robot, **kwargs)
```

### 6.2 生命周期方法

与单区域任务相同：

```python
def build_from_config(self, eval=False, **kwargs):
    super().build_from_config(eval, **kwargs)
    self.reset_entities_positions()
    self.attach_entities_to_arena()

def initialize_episode(self, physics, random_state):
    super().initialize_episode(physics, random_state)
    for key, entity in self.entities.items():
        self.settle_object(key, entity, physics)
```

### 6.3 reset_entities_positions

使用 `composite_entities` 而非 `all_entities`：

```python
def reset_entities_positions(self):
    if self.config_manager.composite_entities is not None:
        entities = self.config_manager.composite_entities
        for k in entities:
            entity = self.entities.get(f"{k}", None)
            if entity is None:
                continue
            height = entity.get_placement_height()
            entity.init_pos[2] += height
```

### 6.4 get_expert_skill_sequence

```python
def get_expert_skill_sequence(self, physics):
    target_entity = self.config_manager.target_entity
    target_container = self.config_manager.target_container

    target_entities = target_entity[0]      # 区域 0 的物体
    target_container_1 = target_container[1][0]  # 区域 1 的容器

    skill_sequence = []
    for entity in target_entities:
        skill_sequence.extend([
            partial(SkillLib.pick, target_entity_name=entity),
            partial(SkillLib.place, target_container_name=target_container_1),
            partial(SkillLib.observe),
        ])
    skill_sequence.extend([partial(SkillLib.end)])
    skill_sequence = self.remove_second_last(skill_sequence)
    return skill_sequence
```


## 七、完整构建流程

### 第一步：明确任务要素

- 确定有几个操作区域
- 每个区域的 `fixture_surface`、`destination_position`
- 每个区域的物体、容器、干扰物
- 共享的 `robocasa_scene`

### 第二步：task_config.json 添加配置块

```json
"文件名": {
    "robot": {
        "position": [x, y, z],
        "euler": [roll, pitch, yaw]
    },
    "task": {
        "asset": {
            "composite_configs": [
                { ... },
                { ... }
            ],
            "robocasa_scene": "场景名"
        },
        "components": [],
        "scene": {"name": "empty"}
    }
}
```

### 第三步：configs/__init__.py 添加映射

```python
"文件名": ["任务名"],
```

### 第四步：编写 .py 任务文件

```python
from functools import partial
from RMMBench.tasks.robocasa_task.base import CompositeNavigationTask
from RMMBench.tasks.config_manager import CompositeNavigationConfigManager
from RMMBench.utils.register import register
from RMMBench.utils.skill_lib import SkillLib

@register.add_config_manager("任务名")
class XxxConfigManager(CompositeNavigationConfigManager):
    def __init__(self, task_name, num_objects=[...], **kwargs):
        super().__init__(task_name, num_objects, **kwargs)
        self.LAYOUT_CONFIG_TABLE = [...]
        self.CONTAINER_CONFIG_TABLE = [...]

    def get_instruction(self, target_entity, target_container, **kwargs):
        ...

    def get_condition_config(self, **kwargs):
        ...

    def reorder_target_object_info(self):
        pass

@register.add_task("任务名")
class XxxTask(CompositeNavigationTask):
    def __init__(self, task_name, robot, **kwargs):
        self.attach_objects = [...]
        super().__init__(task_name, robot=robot, **kwargs)

    def build_from_config(self, eval=False, **kwargs):
        ...

    def initialize_episode(self, physics, random_state):
        ...

    def reset_entities_positions(self):
        ...

    def attach_entities_to_arena(self):
        ...

    def get_expert_skill_sequence(self, physics):
        ...
```

### 第五步：robocasa_task/__init__.py 添加导入

```python
from RMMBench.tasks.robocasa_task.文件名 import *
```

### 第六步：验证一致性

```
task_config.json 的 key       ==  .py 文件名（不含 .py）
configs/__init__.py 的 key    ==  .py 文件名
configs/__init__.py 的 value  ==  register 装饰器参数
robocasa_task/__init__.py     ==  from ...文件名 import *
```


## 八、参考模板

| 场景类型 | 参考文件 | 特点 |
|---------|---------|------|
| 双区域 + 导航 + 放置 | `test_wraparound.py` | `select_bread_to_plate`，mid_container + 导航条件 |
| 双区域 + 零食收纳 | `composite_organize_snacks.py` | `organize_snacks_to_tray`，多物体 + 单容器 |


## 九、常见错误与注意事项

1. **忘记设置 `LAYOUT_CONFIG_TABLE`**：基类不会自动填充，子类必须覆盖，否则 `get_object_info_for_layout` 会越界或行为异常。

2. **`CONTAINER_CONFIG_TABLE` 长度不匹配**：数组长度应等于 `composite_configs` 数量。无容器的 layout 用 `{}` 占位。

3. **`num_objects` 长度**：应与 `composite_configs` 长度一致，表示每个 layout 的物体数量。

4. **`merged_seen_object` 访问**：是嵌套列表，访问具体物体用 `self.merged_seen_object[layout_idx][obj_idx]`。

5. **`target_bbox` 自动生成**：基类 `_get_layout_stop_point` 会自动从 `work_info[idx]` 生成导航停止点，子类只需在 `get_condition_config` 中引用。

6. **`target_object_info` 必须填充**：每个 layout 的 `target_object_info` 需要手动设置 `target_bbox` 和 `target_orientation`，供导航条件使用。

7. **`ordered_indices` 含义**：指定哪些步骤必须按顺序完成。如 `[0, 1]` 表示 Step 0 和 Step 1 必须按顺序，Step 2 可以在任何时候完成。

8. **机器人类型**：复合导航任务必须使用带移动底盘的机器人（如 `pandaomron`），固定机械臂无法完成跨区域导航。
