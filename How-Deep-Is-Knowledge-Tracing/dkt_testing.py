# -*- coding: utf-8 -*-
"""DKT testing for Xiulei.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1mGvhNaXV5PbsLWdRLZNJkOhO7G4V_hBw

# 1. Plot metrics after training
"""

import pandas as pd
import matplotlib.pyplot as plt
import tensorflow as tf
import seaborn as sns
import numpy as np
import keras

from keras.preprocessing import sequence
from keras.utils import np_utils
from keras.models import Sequential
from keras.layers import TimeDistributed, Dense, Masking
from keras.layers.recurrent import LSTM
from keras import backend as K


df = pd.read_csv('/content/assistments.txt.history.txt', sep='\t', names=['Train loss', 'Test loss', 
                                                         'Mean train loss', 'Mean test loss',
                                                         'AUC train', 'AUC test'])

plt.figure(figsize=(10, 6))
df['AUC train'].plot()
df['AUC test'].plot()
plt.title("AUC")
plt.xlabel("Training Steps")
plt.legend()
plt.grid()
plt.show()

plt.figure(figsize=(10, 6))
df['Train loss'].plot()
df['Test loss'].plot()
plt.title("Total loss")
plt.xlabel("Training Steps")
plt.legend()
plt.grid()
plt.show()

plt.figure(figsize=(10, 6))
df['Mean train loss'].plot()
df['Mean test loss'].plot()
plt.title("Mean loss")
plt.xlabel("Training Steps")
plt.legend()
plt.grid()
plt.show()

"""# 2. Plot predictions using pre-trained weights """

# https://groups.google.com/forum/#!msg/keras-users/7sw0kvhDqCw/QmDMX952tq8J
def pad_sequences(sequences, maxlen=None, dim=1, dtype='int32',
    padding='pre', truncating='pre', value=0.):
    '''
        Override keras method to allow multiple feature dimensions.

        @dim: input feature dimension (number of features per timestep)
    '''
    lengths = [len(s) for s in sequences]

    nb_samples = len(sequences)
    if maxlen is None:
        # maxlen = np.max(lengths)
        maxlen = tf.max(lengths)

    x = (np.ones((nb_samples, maxlen, dim)) * value).astype(dtype)
    for idx, s in enumerate(sequences):
        if truncating == 'pre':
            trunc = s[-maxlen:]
        elif truncating == 'post':
            trunc = s[:maxlen]
        else:
            raise ValueError("Truncating type '%s' not understood" % padding)

        if padding == 'post':
            x[idx, :len(trunc)] = trunc
        elif padding == 'pre':
            x[idx, -len(trunc):] = trunc
        else:
            raise ValueError("Padding type '%s' not understood" % padding)
    return tf.convert_to_tensor(x)


def load_dataset(dataset, split_file):
    seqs, num_skills = read_file(dataset)
    
    with open(split_file, 'r') as f:
        student_assignment = f.read().split(' ')
    
    training_seqs = [seqs[i] for i in range(0, len(seqs)) if student_assignment[i] == '1']
    testing_seqs = [seqs[i] for i in range(0, len(seqs)) if student_assignment[i] == '0']
    
    return training_seqs, testing_seqs, num_skills
    

def read_file(dataset_path):
    seqs_by_student = {}
    problem_ids = {}
    next_problem_id = 0
    with open(dataset_path, 'r') as f:
        for line in f:
            student, problem, is_correct = line.strip().split(' ')
            student = int(student)
            if student not in seqs_by_student:
                seqs_by_student[student] = []
            if problem not in problem_ids:
                problem_ids[problem] = next_problem_id
                next_problem_id += 1
            seqs_by_student[student].append((problem_ids[problem], int(is_correct == '1')))
    
    sorted_keys = sorted(seqs_by_student.keys())
    return [seqs_by_student[k] for k in sorted_keys], next_problem_id


def loss_function(y_true, y_pred):
    skill = y_true[:,:,0:num_skills]
    obs = y_true[:,:,num_skills]
    rel_pred = tf.reduce_sum(y_pred * skill, axis=2)
    
    # keras implementation does a mean on the last dimension (axis=-1) which
    # it assumes is a singleton dimension. But in our context that would
    # be wrong.
    return K.binary_crossentropy(rel_pred, obs)


dataset = "assistments.txt"
split_file = "assistments_split.txt"
hidden_units = 200
batch_size = 5
time_window = 100
epochs = 50

training_seqs, testing_seqs, num_skills = load_dataset(dataset, split_file)


# build model
model = Sequential()

# ignore padding
model.add(Masking(-1.0, batch_input_shape=(batch_size, time_window, num_skills*2)))

# lstm configured to keep states between batches
# model.add(LSTM(input_dim = num_skills*2, 
#                output_dim = hidden_units, 
#                return_sequences=True,
#                batch_input_shape=(batch_size, time_window, num_skills*2),
#                stateful = True
# ))

model.add(LSTM(hidden_units, 
                return_sequences=True,
                stateful=True))


# readout layer. TimeDistributedDense uses the same weights for all
# time steps.
# model.add(TimeDistributedDense(input_dim = hidden_units, 
#     output_dim = num_skills, activation='sigmoid'))

model.add(TimeDistributed(Dense(num_skills, activation='sigmoid')))

# optimize with rmsprop which dynamically adapts the learning
# rate of each weight.
# model.compile(loss=loss_function,
#            optimizer='rmsprop', class_mode="binary")
model.compile(loss=loss_function, optimizer='rmsprop')

model.load_weights('model_best_weights.h5')

# Set the id of a sequence from testing_seqs
testing_seqs_id = 52
batch_id = testing_seqs_id // 5

for start_from in range(5 * batch_id, 5 * (batch_id + 1), batch_size):
    end_before = min(len(testing_seqs), start_from + batch_size)
    x = []
    y = []
    # code seqs
    for seq in testing_seqs[start_from:end_before]:
        x_seq = []
        y_seq = []
        # code x questions - input to the model
        xt_zeros = [0 for i in range(0, num_skills*2)] 
        # code y skills - output/ground true 
        ct_zeros = [0 for i in range(0, num_skills+1)]
        xt = xt_zeros[:]
        for skill, is_correct in seq: 
            # add zeros in the beginning 
            x_seq.append(xt) 
            
            # y vector
            ct = ct_zeros[:]
            ct[skill] = 1
            ct[num_skills] = is_correct
            y_seq.append(ct)
            
            # one hot encoding of (last_skill, is_correct)
            pos = skill * 2 + is_correct
            xt = xt_zeros[:]
            xt[pos] = 1
        
        x.append(x_seq)
        y.append(y_seq)
    
    maxlen = max([len(s) for s in x])
    maxlen = time_window

    X = pad_sequences(x, padding='post', maxlen = maxlen, dim=num_skills*2, value=-1.0)
    Y = pad_sequences(y, padding='post', maxlen = maxlen, dim=num_skills+1, value=-1.0)

preds = model.predict(X)

batch_id = testing_seqs_id % 5
output = preds[batch_id].T
print(output.shape)
answers = []
ques = []

for i in range(len(testing_seqs[testing_seqs_id])):
    ques.append(testing_seqs[testing_seqs_id][i][0])
    answers.append(testing_seqs[testing_seqs_id][i][1])

ques_unique = list(set(np.array(ques)))
print(ques_unique)
output = output[ques_unique, :]
output = np.vstack([output[:, 1:len(testing_seqs[testing_seqs_id])+1], np.array(answers)])
print(output.shape)

plt.figure(figsize=(21, 10))
sns.heatmap(np.round(output, 5), annot=True, cmap="YlGnBu", xticklabels=ques, 
                yticklabels=ques_unique + ['Answer'])

plt.xlabel('Time')
plt.ylabel('Questions')
plt.title('Probabilities of Correctness')
# plt.savefig(f'prob1.png', format="PNG")
plt.show()

