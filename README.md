# Using this template

This repo serves as a generic template for all conversion projects undertaken by the CatalystNeuro team. You can easily use this by...

Creating a new project under the CatalystNeuro umbrella (or fork this repo and use it for your personal repos)...

![image](https://user-images.githubusercontent.com/51133164/167436507-8b30ca9d-588c-4941-8385-bdff050f6558.png)


Select this template at the top...

![image](https://user-images.githubusercontent.com/51133164/167436692-670480f1-216d-4cac-a1b3-76ad518ec2f6.png)



# Setting up pre-commit bot

For new repos, an extra step of allowing the black auto-commit CI bot may have to be enabled at: https://results.pre-commit.ci/



# Dataset-specific environments

If the conversion involves multiple very different datasets collected over several years it is recommended to have separate environments for each dataset to reconcile dependency conflicts, instead of attempting to either keep old conversions up to date with recent upstream changes or using strong version pinning at the outer level `my-lab-to-nwb` requirements.

These environments can be easily made by simply calling

```
conda create name_of_environment_file.yml
conda activate name-of-environment
```

Of course, if the conversion is sufficiently simple feel free to keep dependencies at the outermost level.
