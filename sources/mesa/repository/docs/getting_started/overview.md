# MESA: An Evaluation Framework for Compositional, Semantic, and Spatial Generalization in Robotics

```{image} /images/MESA.png
:alt: MESA benchmark overview
:width: 650px
```

Welcome to MESA, a dynamic evaluation framework designed to probe language steering and precisely measure language-conditioned policy
generalization. Our framework includes **MESA-Gen**, a pipeline for scalable task and demonstration generation built upon substantial improvements to MimicGen. We also provide **MESA-Bench**, a benchmark designed to probe generalization to unseen spatial configurations, object instances, object categories, and subtask compositions for tabletop manipulation tasks.

This repository enables you to:
1. Design your own tabletop manipulation task suites, either using one of our task skeletons or one that you've defined.
2. Collect a small number of demonstrations for your tasks as needed. 
3. Expand and diversify your dataset using MESA-Gen.
4. Easily run evaluations using your dataset, including new metrics to better measure language-following beyond success rates.

## MESA-Bench

Our benchmark consists of a canonical training set (**MESA-70**) and the 5 following evaluation suites:
- A suite evaluating in-distribution performance
- **MESA-Spatial** - evaluates seen tasks with unseen spatial configurations
- **MESA-Category** - evaluates tasks with unseen object categories
- **MESA-Instance** - evaluates seen tasks with unseen object instances
- **MESA-Composite** - evaluates unseen composite tasks comprised of in-distribution subtasks

You can download our training set along with our evaluation sets from [Hugging Face](https://huggingface.co/collections/albertwilcox/mesa).

## BiMESA-Bench

BiMESA is the dual-arm extension of MESA, built on a two-arm reverse-mounted YAM platform. It adds coordination skills with no single-arm analogue — cross-arm handoffs and articulated-fixture manipulation. The **BiMESA-57** training set spans three skill blocks (spatial pick-and-place, handoff, and single-arm articulated), evaluated by five suites: an in-distribution suite plus held-out spatial configurations, object instances, object categories, and subtask compositions. See the [bimanual task suites](/mesa_bench/task_suites_bimanual.md) for the full task list.

## Citation
This is the official repository for the paper ''MESA: An Evaluation Framework for Compositional, Semantic, and Spatial Generalization in Robotics'' (CoRL 2026).

We would also like to thank the authors of MimicLabs, RoboCasa, MimicGen, LIBERO, RoboMimic, and Robosuite.

If you have found MESA useful, please cite in your work:
```bibtex
@inproceedings{wilcox2026mesa,
  author    = {Albert Wilcox and Frank Chang and Nhi Nguyen and Aishani Chakraborty and Jeremy A. Collins and Vaibhav Saxena and Benjamin Joffe and Siddharth Karamcheti and Animesh Garg},
  title     = {{MESA}: An Evaluation Framework for Compositional, Semantic, and Spatial Generalization in Robotics},
  booktitle = {10th Annual Conference on Robot Learning},
  year      = {2026},
  url       = {https://openreview.net/forum?id=Br2rXixvyN},
}
```
