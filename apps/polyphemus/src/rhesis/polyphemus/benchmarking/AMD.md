# Torch installation Guide for AMD GPU
This Guide is aimed towards AMD Graphics Card Users.
This is verified using only one Arch Linux system.
If you have any other experiences, please add them here

## Arch Linux
Install the ROCm components on the system needed for torch
```
sudo pacman -Su python-pytorch-rocm
```

For the next step, if you have torch installed already, you need to remove it:

```
uv pip uninstall torch torchvision torchaudio
```

Then you need to install a specific torch version in python.
You can get the current link from the [pytorch](https://pytorch.org/get-started/locally/) website.
Select your platform and download the right version into your uv environment.
For example:
```
 uv pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.3
```