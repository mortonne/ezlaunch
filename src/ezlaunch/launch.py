"""Command line tools for job management."""

import click
from pathlib import Path
import shutil
import subprocess


def get_batch_file(batch_dir, job_name):
    """Get a file with a job serial number."""
    number = 1
    batch_file = batch_dir / f"{job_name}{number}.sbatch"
    while batch_file.exists():
        number += 1
        batch_file = batch_dir / f"{job_name}{number}.sbatch"
    return batch_file


@click.command()
@click.argument("commands_file", type=click.Path(exists=True))
@click.argument("job_name")
@click.argument("batch_dir", type=click.Path(), envvar="BATCHDIR")
@click.option("--partition", "-p", help="partition to submit to")
@click.option("--nodes", "-N", help="number of nodes for each command")
@click.option("--ntasks", "-n", help="number of tasks for each command")
@click.option("--ntasks-per-node", help="number of tasks per node per command")
@click.option("--cpus-per-task", "-c", help="number of processors per task")
@click.option("--mem-per-cpu", help="minimum memory required per processor")
@click.option(
    "--mail-type", 
    help="event types that should trigger notification; multiple values may be specified, separated by commas (NONE, BEGIN, END, FAIL, REQUEUE, ALL, INVALID_DEPEND, STAGE_OUT, TIME_LIMIT, TIME_LIMIT_90, TIME_LIMIT_80, TIME_LIMIT_50)"
)
@click.option("--mail-user", help="email address to notify")
@click.option(
    "--test-only", 
    help="validate the batch script and return a scheduling estimate",
    is_flag=True,
)
def launch(
    commands_file,
    job_name,
    batch_dir,
    **kwargs,
):
    """
    Launch multiple commands to run in parallel.

    Run commands specified in COMMANDS_FILE in parallel, using a Slurm
    job array if there are multiple commands. Each command must be on a
    separate line.
    
    Job-related files will be stored in BATCH_DIR under JOB_NAME,
    including JOB_NAME.sh (the commands) and JOB_NAME.sbatch (the Slurm
    batch submission file), where JOB_NAME has had a serial number
    appended to it.

    Job output will be stored in JOB_NAME_%j.out and JOB_NAME_%j.err
    for single commands, and JOB_NAME_%A-%a.{out,err} for multiple
    commands, where %j is the jobid, %A is the master job allocation
    number, and %a is the job array ID number.
    """
    # read commands to run in parallel
    with open(commands_file, "r") as f:
        commands = f.readlines()
    if any([l.strip() == "" for l in commands]):
        raise IOError("Commands file contains empty lines")
    n_commands = len(commands)
    
    # set up batch directory
    batch_dir = Path(batch_dir)
    batch_dir.mkdir(exist_ok=True)

    # initialize the batch file
    batch_file = get_batch_file(batch_dir, job_name)
    batch = open(batch_file, "w")
    batch.write("#!/bin/bash\n")

    # write flags
    for name, value in kwargs.items():
        if value is not None:
            opt = f"--{name}".replace("_", "-")
            if isinstance(value, bool):
                if value == True:
                    batch.write(f"#SBATCH {opt}\n")
            else:
                batch.write(f"#SBATCH {opt}={value}\n")

    # if multiple commands, run using a job array
    if n_commands > 1:
        batch.write(f"#SBATCH --array=1-{n_commands}\n")
    
    # output files
    if n_commands > 1:
        suffix = "%A-%a"
    else:
        suffix = "%j"
    base = batch_file.parent / f"{batch_file.stem}_{suffix}"
    output_file = base.with_suffix(".out")
    error_file = base.with_suffix(".err")
    batch.write(f"#SBATCH --output={output_file}\n")
    batch.write(f"#SBATCH --error={error_file}\n\n")

    # get the start time
    batch.write('echo " Job starting at $(date)\n')
    batch.write('start=$(date +%s)\n\n')

    # run the command
    if n_commands > 1:
        batch_commands_file = batch_file.with_suffix(".sh")
        shutil.copyfile(commands_file, batch_commands_file)
        batch.write(f'command=$(sed "${{SLURM_ARRAY_TASK_ID}}q;d" "{batch_commands_file}")\n')
        batch.write('echo " Job command: $command"\n')
        batch.write('eval "$command"\n\n')
    else:
        batch.write(f"{commands[0]}\n")

    # report finish time
    batch.write('echo " Job complete at $(date)"\n')
    batch.write('finish=$(date +%s)\n')
    batch.write('printf "Job duration: %02d:%02d:%02d (%d s)\\n" $(((finish-start)/3600)) $(((finish-start)%3600/60)) $(((finish-start)%60)) $((finish-start))\n')

    batch.close()

    # submit
    process = subprocess.Popen(
        f"sbatch {batch_file}",
        shell=True,
        stdout=subprocess.PIPE,
        encoding='utf-8',
    )
