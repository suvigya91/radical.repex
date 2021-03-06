
__copyright__ = "Copyright 2013-2014, http://radical.rutgers.edu"
__license__ = "MIT"

import os
import sys
import math
import json
import time
import random

#-------------------------------------------------------------------------------
#
def weighted_choice_sub(weights):
    """Adopted from asyncre-bigjob [1]
    """

    rnd = random.random() * sum(weights)
    for i, w in enumerate(weights):
        rnd -= w
        if rnd < 0:
            return i

#-------------------------------------------------------------------------------
#
def gibbs_exchange(r_i, replicas, swap_matrix):
    """Adopted from asyncre-bigjob [1]
    Produces a replica "j" to exchange with the given replica "i"
    based off independence sampling of the discrete distribution

    Arguments:
    r_i - given replica for which is found partner replica
    replicas - list of Replica objects
    swap_matrix - matrix of dimension-less energies, where each column is a replica 
    and each row is a state

    Returns:
    r_j - replica to exchnage parameters with
    """

    #evaluate all i-j swap probabilities
    ps = [0.0]*(len(replicas))

    j = 0
    for r_j in replicas:
        ps[j] = -(swap_matrix[r_i.sid][r_j.id] + swap_matrix[r_j.sid][r_i.id] - 
                  swap_matrix[r_i.sid][r_i.id] - swap_matrix[r_j.sid][r_j.id]) 
        j += 1
        
    ######################################
    new_ps = []
    for item in ps:
        if item > math.log(sys.float_info.max): new_item=sys.float_info.max
        elif item < math.log(sys.float_info.min) : new_item=0.0
        else :
            new_item = math.exp(item)
        new_ps.append(new_item)
    ps = new_ps
    # index of swap replica within replicas_waiting list
    j = len(replicas)
    while j > (len(replicas) - 1):
        j = weighted_choice_sub(ps)
        
    # guard for errors
    if j is None:
        j = random.randint(0,(len(replicas)-1))
        print "...gibbs exchnage warning: j was None..."
    # actual replica
    r_j = replicas[j]
    ######################################

    return r_j

#-------------------------------------------------------------------------------
#
def do_exchange(dimension, replicas, swap_matrix):
    """
    """

    exchanged = []
    for r_i in replicas:
        # does this pick a correct one????
        r_j = gibbs_exchange(r_i, replicas, swap_matrix)
       
        if (r_j.id != r_i.id) and (r_j.id not in exchanged) and (r_i.id not in exchanged):
            exchanged.append(r_j.id)
            exchanged.append(r_i.id)
            
    return  exchanged

#-------------------------------------------------------------------------------

class Replica3d(object):
    """Class representing replica and it's associated data.
       US = Umbrella Sampling
    """
    def __init__(self, my_id, new_temperature=None, new_salt=None, new_restraints=None, rstr_val_1=None, rstr_val_2=None):
       
        self.id = int(my_id)
        self.sid = int(my_id)

        if new_salt is None:
            self.new_salt_concentration = 0
        else:
            self.new_salt_concentration = new_salt
        self.old_salt_concentration = new_salt

        if new_restraints is None:
            self.new_restraints = ''
            self.old_restraints = ''
        else:
            self.new_restraints = new_restraints
            self.old_restraints = new_restraints
        self.potential_1 = 0

        if new_temperature is None:
            self.new_temperature = 0
        else:
            self.new_temperature = new_temperature
        self.old_temperature = new_temperature

        if rstr_val_1 is None:
            self.rstr_val_1 = 0
        else:
            self.rstr_val_1 = rstr_val_1

        if rstr_val_2 is None:
            self.rstr_val_2 = 0
        else:
            self.rstr_val_2 = rstr_val_2

#-------------------------------------------------------------------------------

if __name__ == '__main__':
    """
    """

    argument_list = str(sys.argv)
    replicas = int(sys.argv[1])
    current_cycle = int(sys.argv[2])
    dimension = int(sys.argv[3])

    replica_dict = {}

    replicas_obj = []

    base_name = "matrix_column"

    # init matrix
    swap_matrix = [[ 0. for j in range(replicas)] for i in range(replicas)]

    for rid in range(replicas):
        success = 0
        column_file = base_name + "_" + str(rid) + "_" + str(current_cycle) + ".dat" 
        path = "../staging_area/" + column_file     
        while (success == 0):
            try:
                f = open(path)
                lines = f.readlines()
                f.close()
                
                #---------------------------------------------------------------
                # populating matrix column
                data = lines[0].split()
                for i in range(replicas):
                    swap_matrix[i][int(rid)] = float(data[i])
                #---------------------------------------------------------------
                # populating replica dict
                data = lines[1].split()
                replica_dict[data[0]] = [data[1], data[2], data[3], data[4]]
                #---------------------------------------------------------------
                # updating rstr_val's for a given replica
                rid = data[0]
   
                current_rstr = replica_dict[rid][1]
                try:
                    r_file = open(("../staging_area/" + current_rstr), "r")
                except IOError:
                    print "Warning: unable to access template file: {0}".format(current_rstr)

                tbuffer = r_file.read()
                r_file.close()
                tbuffer = tbuffer.split()

                line = 2
                for word in tbuffer:
                    if word.startswith("r2=") and line == 2:
                        num_list = word.split('=')
                        rstr_val_1 = float(num_list[1])
                    
                # creating replica
                r = Replica3d(rid, new_temperature=replica_dict[rid][2], new_salt=replica_dict[rid][3], new_restraints=replica_dict[rid][1], rstr_val_1=rstr_val_1)
                replicas_obj.append(r)

                success = 1
                print "Success processing replica: %s" % rid

            except:
                print "Waiting for replica: %s" % rid
                time.sleep(1)
                pass

    #---------------------------------------------------------------------------

    d1_list = []
    d2_list = []
    d3_list = []

    exchange_list = []

    for r1 in replicas_obj:
        current_temp = r1.new_temperature
            
        #-----------------------------------------------------------------------
        # temperature exchange
        if dimension == 1:
            r_pair = [r1.new_salt_concentration, r1.rstr_val_1]
            
            if r_pair not in d1_list:
                d1_list.append(r_pair)
                current_group = []

                for r2 in replicas_obj:
                    if (r1.rstr_val_1 == r2.rstr_val_1) and (r1.new_salt_concentration == r2.new_salt_concentration):
                        current_group.append(r2)

                #---------------------------------------------------------------
                # perform exchange among group members
                exchange_pair = do_exchange(dimension, current_group, swap_matrix)
                exchange_list.append(exchange_pair)
        #-----------------------------------------------------------------------
        # salt exchange
        elif dimension == 2:
            #r_pair = [r1.new_temperature, r1.rstr_val_2]
            r_pair = [r1.new_temperature, r1.rstr_val_1]

            if r_pair not in d2_list:
                d2_list.append(r_pair)
                current_group = []
                    
                for r2 in replicas_obj:
                    if (r1.new_temperature == r2.new_temperature) and (r1.rstr_val_1 == r2.rstr_val_1):
                        current_group.append(r2)
                    
                #---------------------------------------------------------------
                # perform exchange among group members
                exchange_pair = do_exchange(dimension, current_group, swap_matrix)
                exchange_list.append(exchange_pair)
        #-----------------------------------------------------------------------
        # us exchange 
        elif dimension == 3:
            #r_pair = [r1.new_temperature, r1.rstr_val_1]
            r_pair = [r1.new_temperature, r1.new_salt_concentration]

            if r_pair not in d3_list:
                d3_list.append(r_pair)
                current_group = []
                    
                for r2 in replicas_obj:
                    if (r1.new_temperature == r2.new_temperature) and (r1.new_salt_concentration == r2.new_salt_concentration):
                        current_group.append(r2)
                    
                #---------------------------------------------------------------
                # perform exchange among group members
                exchange_pair = do_exchange(dimension, current_group, swap_matrix)
                exchange_list.append(exchange_pair)

    #---------------------------------------------------------------------------
    # writing to file

    try:
        outfile = "pairs_for_exchange_{dim}_{cycle}.dat".format(dim=dimension, cycle=current_cycle)
        with open(outfile, 'w+') as f:

            for pair in exchange_list:
                if pair:
                    row_str = str(pair[0]) + " " + str(pair[1]) 
                    f.write(row_str)
                    f.write('\n')
        f.close()

    except IOError:
        print 'Error: unable to create column file %s for replica %s' % (outfile, replica_id)

