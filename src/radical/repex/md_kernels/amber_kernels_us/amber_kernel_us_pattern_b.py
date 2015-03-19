"""
.. module:: radical.repex.md_kernles.amber_kernels_salt.amber_kernel_salt_pattern_b
.. moduleauthor::  <haoyuan.chen@rutgers.edu>
.. moduleauthor::  <antons.treikalis@rutgers.edu>
"""

__copyright__ = "Copyright 2013-2014, http://radical.rutgers.edu"
__license__ = "MIT"

import os
import sys
import time
import math
import json
import random
import shutil
import datetime
from os import path
import radical.pilot
from md_kernels.md_kernel_us import *
from kernels.kernels import KERNELS
from replicas.replica import ReplicaUS
import radical.utils.logger as rul
import amber_kernels_us.amber_matrix_calculator_pattern_b

#-----------------------------------------------------------------------------------------------------------------------------------

class AmberKernelUSPatternB(MdKernelUS):
    """This class is responsible for performing all operations related to Amber for RE scheme S2.
    In this class is determined how replica input files are composed, how exchanges are performed, etc.

    RE pattern B:
    - Synchronous RE scheme: none of the replicas can start exchange before all replicas has finished MD run.
    Conversely, none of the replicas can start MD run before all replicas has finished exchange step. 
    In other words global barrier is present.   
    - Number of replicas is greater than number of allocated resources for both MD and exchange step.
    - Simulation cycle is defined by the fixed number of simulation time-steps for each replica.
    - Exchange probabilities are determined using Gibbs sampling.
    - Exchange step is performed in decentralized fashion on target resource.

    """
    def __init__(self, inp_file,  work_dir_local):
        """Constructor.

        Arguments:
        inp_file - package input file with Pilot and NAMD related parameters as specified by user 
        work_dir_local - directory from which main simulation script was invoked
        """

        MdKernelUS.__init__(self, inp_file, work_dir_local)

        self.pre_exec = KERNELS[self.resource]["kernels"]["amber"]["pre_execution"]
        try:
            self.amber_path = inp_file['input.MD']['amber_path']
        except:
            print "Using default Amber path for %s" % inp_file['input.PILOT']['resource']
            try:
                self.amber_path = KERNELS[self.resource]["kernels"]["amber"]["executable"]
            except:
                print "Amber path for localhost is not defined..."

        #self.amber_restraints = inp_file['input.MD']['amber_restraints']
        self.amber_coordinates = inp_file['input.MD']['amber_coordinates']
        self.amber_parameters = inp_file['input.MD']['amber_parameters']
        self.amber_input = inp_file['input.MD']['amber_input']
        self.input_folder = inp_file['input.MD']['input_folder']
        self.init_temperature = float(inp_file['input.MD']['init_temperature'])
        self.current_cycle = -1

        self.name = 'ak-patternB-us'
        self.logger  = rul.getLogger ('radical.repex', self.name)

        self.shared_urls = []
        self.shared_files = []

    # ------------------------------------------------------------------------------
    # ok
    def prepare_shared_data(self):

        parm_path = self.work_dir_local + "/" + self.inp_folder + "/" + self.amber_parameters
        inp_path  = self.work_dir_local + "/" + self.inp_folder + "/" + self.amber_input

        rstr_list = []
        for rstr in self.restraints_files:
            rstr_list.append(self.work_dir_local + "/" + self.inp_folder + "/" + rstr)

        calc_b = os.path.dirname(amber_kernels_us.amber_matrix_calculator_pattern_b.__file__)
        calc_b_path = calc_b + "/amber_matrix_calculator_pattern_b.py"

        self.shared_files.append(self.amber_parameters)
        self.shared_files.append(self.amber_input)
        for rstr in self.restraints_files:
            self.shared_files.append(rstr)
        self.shared_files.append("amber_matrix_calculator_pattern_b.py")

        parm_url = 'file://%s' % (parm_path)
        self.shared_urls.append(parm_url)

        inp_url = 'file://%s' % (inp_path)
        self.shared_urls.append(inp_url)

        for rstr_p in rstr_list:
            rstr_url = 'file://%s' % (rstr_p)
            self.shared_urls.append(rstr_url)

        calc_b_url = 'file://%s' % (calc_b_path)
        self.shared_urls.append(calc_b_url)


#-----------------------------------------------------------------------------------------------------------------------------------
    # OK
    def build_input_file(self, replica):
        """Builds input file for replica, based on template input file ala10.mdin
        """

        basename = self.inp_basename
            
        new_input_file = "%s_%d_%d.mdin" % (basename, replica.id, replica.cycle)
        outputname = "%s_%d_%d.mdout" % (basename, replica.id, replica.cycle)
        old_name = "%s_%d_%d" % (basename, replica.id, (replica.cycle-1))
        replica.new_coor = "%s_%d_%d.rst" % (basename, replica.id, replica.cycle)
        replica.new_traj = "%s_%d_%d.mdcrd" % (basename, replica.id, replica.cycle)
        replica.new_info = "%s_%d_%d.mdinfo" % (basename, replica.id, replica.cycle)

        if (replica.cycle == 0):
            first_step = 0
        elif (replica.cycle == 1):
            first_step = int(self.cycle_steps)
        else:
            first_step = (replica.cycle - 1) * int(self.cycle_steps)

        #restraints = self.amber_restraints
        #if (replica.cycle == 0):
        #    restraints = self.amber_restraints
        #else:
            ##################################
            # changing first path from absolute 
            # to relative so that Amber can 
            # process it
            ##################################
            #path_list = []
            #for char in reversed(replica.first_path):
            #    if char == '/': break
            #    path_list.append( char )

            #modified_first_path = ''
            #for char in reversed( path_list ):
            #    modified_first_path += char

            #modified_first_path = '../' + modified_first_path.rstrip()
            #restraints = modified_first_path + "/" + self.amber_restraints

        try:
            r_file = open( (os.path.join((self.work_dir_local + "/" + self.input_folder + "/"), self.amber_input)), "r")
        except IOError:
            print 'Warning: unable to access template file %s' % self.amber_input

        tbuffer = r_file.read()
        r_file.close()

        tbuffer = tbuffer.replace("@nstlim@",str(self.cycle_steps))
        tbuffer = tbuffer.replace("@disang@",replica.new_restraints)
        #tbuffer = tbuffer.replace("@rstr@", restraints )
        tbuffer = tbuffer.replace("@temp@",str(self.init_temperature))
        
        replica.cycle += 1

        try:
            w_file = open(new_input_file, "w")
            w_file.write(tbuffer)
            w_file.close()
        except IOError:
            print 'Warning: unable to access file %s' % new_input_file


#-----------------------------------------------------------------------------------------------------------------------------------
    # OK
    def prepare_replicas_for_md(self, replicas, sd_shared_list):
        """Prepares all replicas for execution. In this function are created CU descriptions for replicas, are
        specified input/output files to be transferred to/from target system. Note: input files for first and 
        subsequent simulation cycles are different.

        Arguments:
        replicas - list of Replica objects

        Returns:
        compute_replicas - list of radical.pilot.ComputeUnitDescription objects
        """
        compute_replicas = []
        for r in range(len(replicas)):
            # need to avoid this step!
            self.build_input_file(replicas[r])
            crds = self.work_dir_local + "/" + self.inp_folder + "/" + self.amber_coordinates      

            # in principle restraint file should be moved to shared directory
            #rstr = self.work_dir_local + "/" + self.inp_folder + "/" + self.amber_restraints

            input_file = "%s_%d_%d.mdin" % (self.inp_basename, replicas[r].id, (replicas[r].cycle-1))
            # this is not transferred back
            output_file = "%s_%d_%d.mdout" % (self.inp_basename, replicas[r].id, (replicas[r].cycle-1))

            new_coor = replicas[r].new_coor
            new_traj = replicas[r].new_traj
            new_info = replicas[r].new_info
            old_coor = replicas[r].old_coor
            old_traj = replicas[r].old_traj

            st_out = []
            info_out = {
                'source': new_info,
                'target': 'staging:///%s' % new_info,
                'action': radical.pilot.COPY
            }
            st_out.append(info_out)

            coor_out = {
                'source': new_coor,
                'target': 'staging:///%s' % new_coor,
                'action': radical.pilot.COPY
            }
            st_out.append(coor_out)

            if replicas[r].cycle == 1:
                replica_path = "replica_%d_%d/" % (replicas[r].id, 0)
                crds_out = {
                    'source': self.amber_coordinates,
                    'target': 'staging:///%s' % (replica_path + self.amber_coordinates),
                    'action': radical.pilot.COPY
                }
                st_out.append(crds_out)

                cu = radical.pilot.ComputeUnitDescription()
                cu.executable = self.amber_path
                cu.pre_exec = self.pre_exec
                cu.mpi = self.replica_mpi
                cu.arguments = ["-O", "-i ", input_file, 
                                      "-o ", output_file, 
                                      "-p ", self.amber_parameters, 
                                      "-c ", self.amber_coordinates, 
                                      "-r ", new_coor, 
                                      "-x ", new_traj, 
                                      "-inf ", new_info]

                cu.cores = self.replica_cores
                cu.input_staging = [str(input_file), str(crds)] + sd_shared_list
                cu.output_staging = st_out
                compute_replicas.append(cu)
            else:
                replica_path = "/replica_%d_%d/" % (replicas[r].id, 0)
                old_coor = "../staging_area/" + replica_path + self.amber_coordinates

                cu.input_staging = [str(input_file)] + sd_shared_list
                cu.output_staging = st_out

                cu = radical.pilot.ComputeUnitDescription()
                cu.executable = self.amber_path
                cu.pre_exec = self.pre_exec
                cu.mpi = self.replica_mpi
                cu.arguments = ["-O", "-i ", input_file, 
                                      "-o ", output_file, 
                                      "-p ", self.amber_parameters, 
                                      "-c ", self.amber_coordinates, 
                                      "-r ", new_coor, 
                                      "-x ", new_traj, 
                                      "-inf ", new_info]

                cu.cores = self.replica_cores
                cu.input_staging = [str(input_file)] + sd_shared_list
                cu.output_staging = st_out
                compute_replicas.append(cu)

        return compute_replicas

#-----------------------------------------------------------------------------------------------------------------------------------
    # OK
    def prepare_replicas_for_exchange(self, replicas, shared_data_url):
        """Creates a list of ComputeUnitDescription objects for exchange step on resource.
        Number of matrix_calculator_s2.py instances invoked on resource is equal to the number 
        of replicas. 

        Arguments:
        replicas - list of Replica objects

        Returns:
        exchange_replicas - list of radical.pilot.ComputeUnitDescription objects
        """
        all_restraints = ""
        for r in range(len(replicas)):
            if r == 0:
                all_restraints = str(replicas[r].new_restraints)
            else:
                all_restraints = all_restraints + " " + str(replicas[r].new_restraints)

        all_restraints_list = all_restraints.split(" ")

        exchange_replicas = []
        for r in range(len(replicas)):
           
            # name of the file which contains swap matrix column data for each replica
            basename = self.inp_basename

            cu = radical.pilot.ComputeUnitDescription()
            cu.pre_exec = self.pre_exec
            cu.executable = "python"
            # each scheme has it's own calculator!
            # consider moving this in shared input data folder!
            calculator_path = os.path.dirname(amber_kernels_us.amber_matrix_calculator_pattern_b.__file__)
            calculator = calculator_path + "/amber_matrix_calculator_pattern_b.py" 
            input_file = self.work_dir_local + "/" + self.input_folder + "/" + self.amber_input

            data = {
                "replica_id": str(r),
                "replica_cycle" : str(replicas[r].cycle-1),
                "replicas" : str(len(replicas)),
                "base_name" : str(basename),
                "init_temp" : str(self.init_temperature),
                "amber_path" : str(self.amber_path),
                "shared_path" : str(shared_data_url),
                "amber_input" : str(self.amber_input),
                "amber_parameters": str(self.amber_parameters),
                "all_restraints" : all_restraints_list
            }

            dump_data = json.dumps(data)
            json_data = dump_data.replace("\\", "")
            # in principle we can transfer this just once and use it multiple times later during the simulation
            # cu.input_staging = [str(calculator), str(input_file), str(replicas[r].new_coor)]
            cu.input_staging = [str(calculator), str(input_file)]
            cu.arguments = ["amber_matrix_calculator_pattern_b.py", json_data]
            cu.cores = 1            
            exchange_replicas.append(cu)

        return exchange_replicas




