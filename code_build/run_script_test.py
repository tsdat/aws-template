import subprocess
command = "cd /home/d3k339/projects/tsdat/ingest-buoy && /home/d3k339/projects/tsdat/aws-template/cdk/build/find_modified_pipelines_test.sh"

completed_process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

if completed_process.returncode == 0:
    output = completed_process.stdout
    
    # Parse the newline separated text into a list
    changed_pipelines = output.strip().split()
    print(changed_pipelines)
    
    
else:
    raise Exception(f'Failed to perform git diff: {completed_process.stderr}')