# ezlaunch
Programs for managing job submission through Slurm.

The ezlaunch package is designed to make it easier to submit simple parallel jobs using Slurm. The ezlaunch package provides a simple pure-Python script to quickly generate and submit Slurm jobs, organizing job-related files for easier documentation of submitting jobs and their output.

A [previous version](https://github.com/prestonlab/launch) of ezlaunch was designed to work with the TACC Launcher program to coordinate running commands in parallel. This version instead uses Slurm's job arrays feature, allowing it to be used with clusters that do not have Launcher installed. It should work with all Slurm-based clusters.

## Installation

First, create a Python virtual environment or Conda environment and activate it. Then install the package into your environment:

```bash
pip install git+https://github.com/mortonne/ezlaunch
```

To verify installation, run `which ezlaunch`. That should print the path to the installed program.

## Commands

### ezlaunch

The `ezlaunch` program is designed to make it more convenient to run parallel processing on a cluster. It uses job arrays to run a set of similar tasks in parallel using cluster resources.

The usual way to submit a job to a Slurm scheduler is by manually writing an `sbatch` script. Instead, `ezlaunch` takes information about the job, writes an `sbatch` script, submits it, and organizes job outputs for you. It's designed to make it faster and easier to run parallel jobs.

#### Usage

```bash
ezlaunch [OPTIONS] COMMANDS_FILE JOB_NAME BATCH_DIR
```

Run commands specified in COMMANDS_FILE in parallel, using a Slurm job array
if there are multiple commands. Each command must be on a separate line.

Job-related files will be stored in BATCH_DIR under JOB_NAME, including
JOB_NAME.sh (the commands) and JOB_NAME.sbatch (the Slurm batch submission
file), where JOB_NAME has had a serial number appended to it.

Job output will be stored in JOB_NAME_%j.out and JOB_NAME_%j.err for single
commands, and JOB_NAME_%A-%a.{out,err} for multiple commands, where %j is
the jobid, %A is the master job allocation number, and %a is the job array
ID number.

Run `ezlaunch --help` to see all currently supported options. Also see the [Slurm documentation](https://slurm.schedmd.com/sbatch.html) for more details about how to use the options.

If the environment variable `$BATCHDIR` is set, it will be used if the `BATCH_DIR` argument is not provided. This makes it easier to have one central directory with all job information for a given project; just run `export BATCHDIR=mybatchdir; mkdir -p $BATCHDIR` before calling `ezlaunch`, and `mybatchdir` will be used automatically.

#### Walkthrough

First, write a file with the commands you want to run in parallel. You can write this file by hand or write a program to generate it. You should have one command per line. For example, say we have a commands file like the following:

```bash
>>> cat commands.sh
python script.py 1 4
python script.py 2 4
python script.py 3 4
```

In this example, each command calls a Python script that uses Joblib to run commands on multiple cores:

```bash
>>> cat script.py
from math import sqrt
from joblib import Parallel, delayed
import sys
n = sys.argv[1]
n_jobs = sys.argv[2]
Parallel(n_jobs=n_jobs)(delayed(sqrt)(i ** n) for i in range(12))
```

The example script takes in two commandline inputs, the power and the number of parallel jobs to use. It then calculates numbers from 1 to 12 taken to the nth power. Our job will run 12 calculations at a time in parallel, using three job array components with 4 cores each. To use the script, you must first install Joblib into your Python environment using `pip install joblib`.

(This example is simplified; in this case, the overhead of scheduling a job is much higher than the speed boost from parallel execution. Running in parallel on a cluster is only worthwhile for more computationally intensive programs.)

Next, run `ezlaunch` with options to indicate how you want to run your commands. For example, to use one node per command, with 4 cores, 2G of memory per node, and a time limit of 1 minute, and save output to files starting with `testjob` in the current directory:

```bash
>>> ezlaunch commands.sh testjob . -N 1 -n 4 --mem=2G --time=00:01:00
```

This will allocate the specified resources for *each individual command*. Make sure each command will actually make use of the cores that you request, so that the cluster resources will be used efficiently. In this example, the `script.py` program will use Joblib to run multiple calculations in parallel using the 4 cores allocated to each command.

Running `ezlaunch` should immediately create two files: 

* `testjob1.sh` - a copy of the commands file, with the same base name as other output files for ease of looking up job information later on.
* `testjob1.sbatch` - an `sbatch` script with resource requirements, including a job array with one array job for each command, indicating that Slurm should run those jobs in parallel. It will also display the duration of the job in the output. This file can be submitting using `sbatch` (which `ezlaunch` will call automatically).

Output files have a serial number appended to them; the first time you use a given job name, it will be 1, then 2, etc. This makes it easier to see later what jobs you attempted to run previously, how long they took, and what errors occurred.

When the job finishes, you will have output files:

* `testjob1_XXXXXXX-Y.out` - if there are multiple commands, the job will have an ID (assigned by Slurm) and each command will have an ID.
* `testjob1_XXXXXXX.out` - if there is one command, there will only be one output file with this format.

The default is to have both standard output and standard error written to one file. If the `--split-output` flag is set, then there will also be similarly named `.err` files with standard error.
