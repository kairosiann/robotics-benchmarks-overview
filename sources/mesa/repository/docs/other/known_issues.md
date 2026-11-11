# Known Issues

<!-- - Certain meshes in `lab4` and `lab5` have zero volume, and will error out with mujoco==3.3.0. Works with mujoco==3.1.1. -->
- There is an issue with the Meta Quest tracking in that the tracking freezes when starting to teleoperate a simulated robot. We currently do not not have a fix for this, but a workaround is to make large motions with the controller until the robot starts to move and discard that demonstration (by pressing `B`).

Please make sure to submit a GitHub issue if you run into any issues that are not documented here.