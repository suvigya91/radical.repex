"""
.. module:: radical.repex.amber_kernels.launch_simulation_amber
.. moduleauthor::  <antons.treikalis@rutgers.edu>
"""

__copyright__ = "Copyright 2013-2014, http://radical.rutgers.edu"
__license__ = "MIT"

import os
import sys
import json
from os import path
from amber_tex.amber_tex import *
from repex_utils.replica_cleanup import *
from radical.ensemblemd import EnsemblemdError
from repex_utils.parser import parse_command_line
from radical.ensemblemd import SingleClusterEnvironment


#-------------------------------------------------------------------------------

if __name__ == '__main__':
    """Runs RE simulation using Pattern-B. 
    """
 
    print "********************************************************************"
    print "*              RepEx simulation: AMBER + RE Pattern-B              *"
    print "********************************************************************"

    try:
        work_dir_local = os.getcwd()
        params = parse_command_line()
    
        # get input file
        json_data=open(params.input_file)
        inp_file = json.load(json_data)
        json_data.close()

        # Create a new static execution context with one resource and a fixed
        # number of cores and runtime.

        cluster = SingleClusterEnvironment(
            resource=inp_file['input.PILOT']['resource'],
            cores=int(inp_file['input.PILOT']['cores']),
            walltime=int(inp_file['input.PILOT']['runtime']),
            username=inp_file['input.PILOT']['username'], 
            #project=inp_file['input.PILOT']['project'],
            #queue=inp_file['input.PILOT']['queue'],
            database_name='repex-tests'
        )

        # Allocate the resources.
        cluster.allocate()

        # creating pattern object
        re_pattern = AmberTex(inp_file, work_dir_local)

        # initializing replica objects
        replicas = re_pattern.initialize_replicas()

        re_pattern.add_replicas(replicas)

        # run RE simulation  
        cluster.run(re_pattern, 
                    force_plugin="replica_exchange.static_pattern_3")

        # this is a quick hack
        base = re_pattern.inp_basename + ".mdin"

        # finally we are moving all files to individual replica directories
        move_output_files(work_dir_local, base, replicas ) 

        print "Simulation successfully finished!"
        print "Please check output files in replica_x directories."

    except:
        print "Unexpected error:", sys.exc_info()[0]
        raise
    