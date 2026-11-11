# Object Organization

Objects are organized at two levels:
1. Object categories: These are the general classes of objects, e.g. "apple", "banana", "bottle", etc.
2. Object instances: These are the specific instances of an object category, e.g. "apple_1", "apple_2", "banana_1", "banana_2", etc.

Each object instance has a unique key, which is defined in `mesa.sim.envs.objects`. The simulation engine uses these keys and only these keys when instantiating objects.

Object categories are defined in `mesa.sim.task_gen.object_categories`. This file contains information relevant to task generation, such as object affordances, natural language descriptions, and regex patterns for matching object instances. At task generation time, we mainly build variants operating on object categories, and then resolve them into instances at the end of the task generation process.