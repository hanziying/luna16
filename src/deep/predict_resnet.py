from __future__ import division
import sys
import params
import numpy as np
import os
import skimage.io

model_folder = '../../models/'

if len(sys.argv) < 2:
    print "Missing arguments, first argument is model name, second is epoch"
    quit()

model_folder = os.path.join(model_folder, sys.argv[1])

#Overwrite params, ugly hack for now
params.params = params.Params(['../../config/default.ini'] + [os.path.join(model_folder, 'config.ini')])
from params import params as P

if __name__ == "__main__":
    import theano
    import theano.tensor as T
    import lasagne
    sys.path.append('./resnet')
    import util
    from dataset_2D import load_images
    from parallel import ParallelBatchIterator
    from functools import partial
    from tqdm import tqdm
    from glob import glob
    import resnet
    import pandas as pd
    print "Defining network"

    input_var = T.tensor4('inputs')
    target_var = T.ivector('targets')

    network = resnet.ResNet_FullPre_Wide(input_var, P.DEPTH, P.BRANCHING_FACTOR)

    epoch = sys.argv[2]
    subsets = sys.argv[3]

    model_save_file = os.path.join(model_folder, P.MODEL_ID+"_epoch"+epoch+'.npz')

    print "Loading saved model", model_save_file
    with np.load(model_save_file) as f:
         param_values = [f['arr_%d' % i] for i in range(len(f.files))]
    lasagne.layers.set_all_param_values(network, param_values)
    train_fn, val_fn, l_r = resnet.define_updates(network, input_var, target_var)

    in_pattern = '../../data/cadV2_0.5mm_64x64_xy_xz_yz/subset[{}]/*/*.pkl.gz'.format(subsets)
    filenames = glob(in_pattern)[:100]

    batch_size = 128
    multiprocess = False

    def get_images_with_filenames(filenames):
        inputs, targets = load_images(filenames, deterministic=True)
        return inputs, targets, filenames


    gen = ParallelBatchIterator(get_images_with_filenames,
                                        filenames, ordered=True,
                                        batch_size=batch_size,
                                        multiprocess=multiprocess)

    predictions_file = os.path.join(model_folder, 'predictions_subset{}_epoch{}_model{}.csv'.format(subsets,epoch,P.MODEL_ID))
    candidates = pd.read_csv('../../data/candidates_V2.csv')

    print "Predicting {} patches".format(len(filenames))


    all_probabilities = []
    all_filenames = []

    for i, batch in enumerate(tqdm(gen)):
        inputs, targets, filenames = batch
        print len(inputs)
        print len(list(set(filenames)))
        targets = np.array(np.argmax(targets, axis=1), dtype=np.int32)
        err, l2_loss, acc, predictions, predictions_raw = val_fn(inputs, targets)

        print "Loss", err
        print "Accuracy", acc
        print "Average prediction", np.mean(predictions_raw)

        all_probabilities += predictions_raw
        all_filenames += filenames


    print zip(all_filenames[:10], all_probabilities[:10])
