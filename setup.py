from setuptools import setup, find_packages

setup(
    name="neuropack",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'torch',
        'torchvision',
        'torchaudio',
        'numpy',
        'psutil',
        'GPUtil',
        'aiohttp',
        'asyncio',
        'zeroconf'
    ],
)