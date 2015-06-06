"""
.. module:: radical.repex.md_kernels.amber_kernels_tex.amber_kernel_tex_pattern_c
.. moduleauthor::  <antons.treikalis@rutgers.edu>
"""

__copyright__ = "Copyright 2013-2014, http://radical.rutgers.edu"
__license__ = "MIT"

import os
import sys
from os import path
import radical.pilot
import radical.utils.logger as rul
from md_kernels.md_kernel_tex import *

#-----------------------------------------------------------------------------------------------------------------------------------

class AmberKernelTexPatternC(MdKernelTex):
    """This class is responsible for performing all operations related to Amber for RE scheme S2.
    In this class is determined how replica input files are composed, how exchanges are performed, etc.
    """
    def __init__(self, inp_file,  work_dir_local):
        """Constructor.

        Arguments:
        inp_file - package input file with Pilot and NAMD related parameters as specified by user 
        work_dir_local - directory from which main simulation script was invoked
        """

        MdKernelTex.__init__(self, inp_file, work_dir_local)

        self.name = 'ak-tex-patternC'
        self.logger  = rul.getLogger ('radical.repex', self.name)

#-----------------------------------------------------------------------------------------------------------------------------------

    def check_replicas(self, replicas):
        """
        """
        finished_replicas = []
        files = os.listdir( self.work_dir_local )

        for r in replicas:

            history_name =  r.new_history
            for item in files:
                if (item.startswith(history_name)):
                    if r not in finished_replicas:
                        finished_replicas.append( r )

        return finished_replicas


#-----------------------------------------------------------------------------------------------------------------------------------

    def build_input_file_local(self, replica):
        """Builds input file for replica, based on template input file ala10.mdin
        """

        basename = self.inp_basename
        template = self.inp_basename[:-5] + ".mdin"
            
        new_input_file = "%s_%d_%d.mdin" % (basename, replica.id, replica.cycle)
        outputname = "%s_%d_%d.mdout" % (basename, replica.id, replica.cycle)
        old_name = "%s_%d_%d" % (basename, replica.id, (replica.cycle-1))

        # new files
        replica.new_coor = "%s_%d_%d.rst" % (basename, replica.id, replica.cycle)
        replica.new_traj = "%s_%d_%d.mdcrd" % (basename, replica.id, replica.cycle)
        replica.new_info = "%s_%d_%d.mdinfo" % (basename, replica.id, replica.cycle)

        # may be redundant
        replica.new_history = replica.new_info

        # old files
        replica.old_coor = old_name + ".rst"
        replica.old_traj = old_name + ".mdcrd"
        replica.old_info = old_name + ".mdinfo"

        try:
            r_file = open( (os.path.join((self.work_dir_local + "/amber_inp/"), template)), "r")
        except IOError:
            self.logger.info("Warning: unable to access template file {0}".format( template ) )

        tbuffer = r_file.read()
        r_file.close()

        tbuffer = tbuffer.replace("@nstlim@",str(self.cycle_steps))
        tbuffer = tbuffer.replace("@temp@",str(int(replica.new_temperature)))
        
        replica.cycle += 1

        try:
            w_file = open(new_input_file, "w")
            w_file.write(tbuffer)
            w_file.close()
        except IOError:
            self.logger.info("Warning: unable to access file {0}".format( new_input_file ) )

#-----------------------------------------------------------------------------------------------------------------------------------

    def prepare_replicas_local(self, replicas):
        """Prepares all replicas for execution. In this function are created CU descriptions for replicas, are
        specified input/output files to be transferred to/from target system. Note: input files for first and 
        subsequent simulation cycles are different.
        """
        compute_replicas = []
        for r in range(len(replicas)):
            self.build_input_file_local(replicas[r])
            input_file = "%s_%d_%d.mdin" % (self.inp_basename, replicas[r].id, (replicas[r].cycle-1))

            # this is not transferred back
            output_file = "%s_%d_%d.mdout" % (self.inp_basename, replicas[r].id, (replicas[r].cycle-1))

            new_coor = replicas[r].new_coor
            new_traj = replicas[r].new_traj
            new_info = replicas[r].new_info

            old_coor = replicas[r].old_coor
            old_traj = replicas[r].old_traj
            old_info = replicas[r].old_info

            if replicas[r].cycle == 1:
                cu = radical.pilot.ComputeUnitDescription()
                crds = self.work_dir_local + "/" + self.input_folder + "/" + self.amber_coordinates
                parm = self.work_dir_local + "/" + self.input_folder + "/" + self.amber_parameters

                cu.executable = self.amber_path
                cu.pre_exec = self.pre_exec
                cu.mpi = self.replica_mpi
                cu.arguments = ["-O", "-i ", input_file, "-o ", output_file, "-p ", self.amber_parameters, "-c ", self.amber_coordinates, "-r ", new_coor, "-x ", new_traj, "-inf ", new_info]
                cu.cores = self.replica_cores
                cu.input_staging = [str(input_file), str(crds), str(parm)]
                cu.output_staging = [str(new_coor), str(new_traj), str(new_info)]
                compute_replicas.append(cu)
            else:
                cu = radical.pilot.ComputeUnitDescription()
                
                crds = self.work_dir_local + "/" + self.input_folder + "/" + self.amber_coordinates
                parm = self.work_dir_local + "/" + self.input_folder + "/" + self.amber_parameters
                cu.executable = self.amber_path
                cu.pre_exec = self.pre_exec
                cu.mpi = self.replica_mpi
                cu.arguments = ["-O", "-i ", input_file, "-o ", output_file, "-p ", self.amber_parameters, "-c ", old_coor, "-r ", new_coor, "-x ", new_traj, "-inf ", new_info]
                cu.cores = self.replica_cores

                cu.input_staging = [str(input_file), str(crds), str(parm), str(old_coor)]
                cu.output_staging = [str(new_coor), str(new_traj), str(new_info)]
                compute_replicas.append(cu)

        return compute_replicas