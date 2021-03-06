import io
import os
from setuptools import setup


os.chdir(os.path.abspath(os.path.dirname(__file__)))


req = [
    'lazo-index-service==0.4',
    'numpy',
    'pandas',
    'python-dateutil',
    'scikit-learn',
]
with io.open('README.rst', encoding='utf-8') as fp:
    description = fp.read()
setup(name='datamart_profiler',
      version='0.5.5',
      packages=['datamart_profiler'],
      install_requires=req,
      extras_require={
          'prometheus': ['prometheus_client'],
      },
      description="Data profiling library for Datamart",
      author="Remi Rampin",
      author_email='remi.rampin@nyu.edu',
      maintainer="Remi Rampin",
      maintainer_email='remi.rampin@nyu.edu',
      url='https://gitlab.com/ViDA-NYU/datamart/datamart',
      project_urls={
          'Homepage': 'https://gitlab.com/ViDA-NYU/datamart/datamart',
          'Source': 'https://gitlab.com/ViDA-NYU/datamart/datamart',
          'Tracker': 'https://gitlab.com/ViDA-NYU/datamart/datamart/issues',
      },
      long_description=description,
      license='BSD-3-Clause',
      keywords=['datamart'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Science/Research',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Scientific/Engineering :: Information Analysis'])
