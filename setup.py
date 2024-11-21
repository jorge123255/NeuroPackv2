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
        'zeroconf',
        'websockets>=11.0.3',
        'fastapi>=0.104.1',
        'uvicorn>=0.24.0',
        'networkx>=3.2.1',
        'rich>=10.0.0',
        'aiofiles>=23.2.1',
        'jinja2>=3.1.2'
    ],
    entry_points={
        'console_scripts': [
            'neuropack-master=neuropack.distributed.run_master:main',
        ],
    }
)