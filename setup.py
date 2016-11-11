import sys
from setuptools import setup

if len(set(('test', 'easy_install')).intersection(sys.argv)) > 0:
    import setuptools

tests_require = ['dill', 'pygraphviz']

extra_setuptools_args = {}
if 'setuptools' in sys.modules:
    tests_require.append('nose')
    extra_setuptools_args = dict(
        test_suite='nose.collector',
        extras_require=dict(
            test='nose>=0.10.1')
    )

setup(
    name="rsbhsm",
    version="0.2.0",
    description="An RSB extension for transitions",
    author='Alexander Neumann',
    author_email='aleneum@gmail.com',
    url='http://github.com/aleneum/rsbhsm',
    download_url='https://github.com/aleneum/rsbhsm/archive/0.1.0.zip',
    packages=["rsbhsm"],
    package_data={'rsbhsm': ['data/*'],
                  'rsbhsm.tests': ['data/*']
                  },
    install_requires=['six'],
    tests_require=tests_require,
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',

        # not supported by RSB yet
        # 'Programming Language :: Python :: 3',
        # 'Programming Language :: Python :: 3.3',
        # 'Programming Language :: Python :: 3.4',
    ],
    **extra_setuptools_args
)
