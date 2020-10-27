import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
     name='aiopyql',  
     version='PYQLVERSION',
     packages=setuptools.find_packages(include=['aiopyql'], exclude=['build']),
     author="Joshua Jamison",
     author_email="joshjamison1@gmail.com",
     description="A fast and easy-to-use asyncio ORM(Object-relational Mapper) for performing C.R.U.D. ops within RBDMS tables using python",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/codemation/aiopyql",
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
     python_requires='>=3.7, <4',   
     install_requires=['aiosqlite', 'aiomysql'],
 )