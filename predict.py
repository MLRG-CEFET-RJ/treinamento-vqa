import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.misc import imresize
from keras.applications import inception_v3
from keras.models import Model, load_model
from keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import accuracy_score, confusion_matrix
#################################################################
#               Configurando logs de execucao                   #
#################################################################
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='logs/predict.log',
                    filemode='w')
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

#################################################################
#               Configurando logs de execucao                   #
#################################################################
def carregar_triplas(lista_triplas):
    image_triples = pd.read_csv(lista_triplas, sep=",", header=0, names=["left","right","similar"])
    return image_triples.values
#################################################################
def load_image_cache(image_cache, image_filename):
    image = plt.imread(os.path.join(IMAGE_DIR, image_filename))
    image = imresize(image, (299, 299))
    image = image.astype("float32")
    image = inception_v3.preprocess_input(image)
    image_cache[image_filename] = image
################################################################
def pair_generator(triples, image_cache, datagens, batch_size=32):    
    while True:
        # shuffle once per batch
        indices = np.random.permutation(np.arange(len(triples)))        
        num_batches = len(triples) // batch_size        
        for bid in range(num_batches):
            
            batch_indices = indices[bid * batch_size : (bid + 1) * batch_size]
            
            batch = [triples[i] for i in batch_indices]
            X1 = np.zeros((batch_size, 299, 299, 3))
            X2 = np.zeros((batch_size, 299, 299, 3))
            Y = np.zeros((batch_size, 2))
            for i, (image_filename_l, image_filename_r, label) in enumerate(batch):                
                if datagens is None or len(datagens) == 0:
                    X1[i] = image_cache[image_filename_l]
                    X2[i] = image_cache[image_filename_r]
                else:
                    X1[i] = datagens[0].random_transform(image_cache[image_filename_l])
                    X2[i] = datagens[1].random_transform(image_cache[image_filename_r])
                Y[i] = [1, 0] if label == 0 else [0, 1]
            yield [X1, X2], Y
################################################################
def predizer(model):    
    ytest, ytest_ = [], []    
    test_pair_gen = pair_generator(triples_data, image_cache, None, BATCH_SIZE)    
    num_test_steps = len(triples_data) // BATCH_SIZE
    curr_test_steps = 0
    for [X1test, X2test], Ytest in test_pair_gen:
        if curr_test_steps > num_test_steps:
            break        
        Ytest_ = model.predict([X1test, X2test])
        ytest.extend(np.argmax(Ytest, axis=1).tolist())
        ytest_.extend(np.argmax(Ytest_, axis=1).tolist())
        curr_test_steps += 1
    acc = accuracy_score(ytest, ytest_)
    cm = confusion_matrix(ytest, ytest_)
    return acc, cm, ytest
    #return ytest
################################################################


DATA_DIR = os.environ["DATA_DIR"]
FINAL_MODEL_FILE = os.path.join(DATA_DIR, "models", "inception-ft-final-500.h5")
TRIPLES_FILE = os.path.join(DATA_DIR, "triplas_imagenet_vqa.csv") 
IMAGE_DIR = os.path.join(DATA_DIR,"imagenet_vqa")


logger.debug("DATA_DIR %s", DATA_DIR)
logger.debug("FINAL_MODEL_FILE %s", FINAL_MODEL_FILE)
logger.debug("TRIPLES_FILE %s", TRIPLES_FILE)
logger.debug("IMAGE_DIR %s", IMAGE_DIR)

triples_data = carregar_triplas(TRIPLES_FILE)

logger.debug( "Numero de pares : %d",  len(triples_data))

image_cache = {}
num_pairs = len(triples_data)
logger.debug( "carregando imagens")

for i, (image_filename_l, image_filename_r, _) in enumerate(triples_data):    
    if image_filename_l not in image_cache:
        load_image_cache(image_cache, image_filename_l)
    if image_filename_r not in image_cache:
        load_image_cache(image_cache, image_filename_r)

logger.info("imagens carregadas")

test_pair_gen = pair_generator(triples_data, image_cache, None, None)

logger.info("Carregando o modelo")
model = load_model(FINAL_MODEL_FILE)
logger.info("Modelo carregado com sucesso")

BATCH_SIZE = 5

acc,cm, y = predizer(model)
    

logger.info("Finalizado")
