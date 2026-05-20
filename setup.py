import os
import sys
import platform
from setuptools import setup, Extension

class get_pybind_include(object):
    def __str__(self):
        import pybind11
        return pybind11.get_include()

extra_compile_args = []
if platform.system() == "Windows":
    extra_compile_args = ["/std:c++17", "/O2"]
else:
    extra_compile_args = ["-std=c++17", "-O3"]
    # Check architecture to apply native vectorization safely
    if platform.machine().lower() in ["x86_64", "amd64"]:
        extra_compile_args.append("-march=native")

ext_modules = [
    Extension(
        'cpp_accel',
        ['cpp/cpp_accel.cpp'],
        include_dirs=[
            get_pybind_include(),
            os.path.join(os.getcwd(), 'cpp')
        ],
        language='c++',
        extra_compile_args=extra_compile_args
    ),
]

setup(
    name='cpp_accel',
    version='0.1',
    ext_modules=ext_modules,
    zip_safe=False,
)
