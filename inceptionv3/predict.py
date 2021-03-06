import os, sys, time, logging

#os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
#os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
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
def carregar_pares(vqa_file, synset_dir):
    image_pairs = []
    synset_path = os.path.join(IMAGENET_DIR, synset_dir)
    if os.path.isdir(synset_path):
        for imagenet_file in os.listdir(synset_path):
            image_pairs.append( [vqa_file, os.path.join(synset_dir, imagenet_file)])
    else:
        logger.debug("%s nao existe", synset_path)        
    return image_pairs

#################################################################

def tic():
    global _start_time 
    _start_time = time.time()

def tac():
    t_sec = round(time.time() - _start_time)
    (t_min, t_sec) = divmod(t_sec,60)
    (t_hour,t_min) = divmod(t_min,60) 
    logger.info('Time passed: {}hour:{}min:{}sec'.format(t_hour,t_min,t_sec))    

def load_image_cache(image_cache, image_filename, directory):
    try:
        if(image_filename not in image_cache):
            image = Image.open(os.path.join(directory, image_filename)).convert("RGB")
            image = imresize(image, (299, 299))
            image = image.astype("float32")
            image = inception_v3.preprocess_input(image)
            image_cache[image_filename] = image
    except Exception as e:
        logger.warn("Falha ao ler o arquivo [%s]", os.path.join(directory, image_filename))
        logger.error(e)
        sys.exit()        
################################################################
def pair_generator(triples, image_cache, datagens, batch_size=32):    
    while True:
        # shuffle once per batch
        #indices = np.random.permutation(np.arange(len(triples)))        
        indices = np.array( range(0, len(triples)-1))
        num_batches = len(triples) // batch_size        
        for bid in range(num_batches):            
            batch_indices = indices[bid * batch_size : (bid + 1) * batch_size]            
            batch = [triples[i] for i in batch_indices]
            X1 = np.zeros((batch_size, 299, 299, 3))
            X2 = np.zeros((batch_size, 299, 299, 3))
            
            for i, (image_filename_l, image_filename_r) in enumerate(batch):                
                if datagens is None or len(datagens) == 0:                   
                    X1[i] = image_cache[image_filename_l]
                    X2[i] = image_cache[image_filename_r]                    
                else:
                    X1[i] = datagens[0].random_transform(image_cache[image_filename_l])
                    X2[i] = datagens[1].random_transform(image_cache[image_filename_r])
            yield [X1, X2]
################################################################
def predizer(model, generator, steps):
    ytest_ = []
    curr_test_steps = 0
    
    #logger.debug( "NUM STEPS : %d",  steps)
            
    for [X1test, X2test] in test_pair_gen:
        if curr_test_steps >= steps:
            break        
        y = model.predict([X1test, X2test])      
        #ytest_.extend(np.argmax(y, axis=1).tolist())
        #retornando o score ao inves da similaridade
        ytest_.extend([y[0,1]])
        if(curr_test_steps % 10 == 0):
            logger.debug("Current step %s", curr_test_steps)
        curr_test_steps += 1                
    return ytest_
################################################################
def load_synset_list(path):
    df = pd.read_csv(path, names=["synset"], encoding="utf-8", header=1)
    return df.values
################################################################
def load_vqa_filenames_list(path):
    df = pd.read_csv(path, names=["filename"], encoding="utf-8", header=1)
    return df.values
################################################################
DATA_DIR = os.environ["DATA_DIR"]
#FINAL_MODEL_FILE = os.path.join(DATA_DIR, "models", "inception-ft-best.h5")
FINAL_MODEL_FILE = os.path.join(DATA_DIR, "vqa", "models", "distilation","inception-training-distlation3-ft-best.h5")
TRIPLES_FILE = os.path.join(DATA_DIR, "triplas_imagenet_vqa.csv") 
IMAGE_DIR = DATA_DIR
IMAGENET_DIR = os.path.join(IMAGE_DIR, "ILSVRC", "Data", "DET", "train", "ILSVRC2013_train")
VQA_DIR = os.path.join(IMAGE_DIR, "vqa", "convertidas")
BATCH_SIZE = 128

logger.debug("DATA_DIR %s", DATA_DIR)
logger.debug("FINAL_MODEL_FILE %s", FINAL_MODEL_FILE)
logger.debug("TRIPLES_FILE %s", TRIPLES_FILE)
logger.debug("IMAGE_DIR %s", IMAGE_DIR)

logger.debug("IMAGENET_DIR %s", IMAGENET_DIR)
logger.debug("VQA_DIR %s", VQA_DIR)


logger.info("Carregando o modelo")
model = load_model(FINAL_MODEL_FILE)
logger.info("Modelo carregado com sucesso")

logger.debug( "Carregando pares de imagens...")

logger.debug("BATCH_SIZE %s", BATCH_SIZE)

synsets = load_synset_list(os.path.join(DATA_DIR, "synsets_dog_cat.csv"))
#vqa_filenames_list = load_vqa_filenames_list(os.path.join(DATA_DIR, "mscoco_cats.csv"))

for vqa_file in os.listdir(VQA_DIR):
#for filename in vqa_filenames_list:    
    #vqa_file = filename[0]
    vqa_image_path = os.path.join(VQA_DIR,vqa_file)
    logger.info("processando a imagem [%s]", vqa_image_path)
    similarities = []
    
    #for synset_dir in os.listdir(IMAGENET_DIR):
    for synset in synsets:
        synset_dir = synset[0]
        logger.info("processando o synset [%s]", synset_dir)
        pairs_data = carregar_pares(vqa_file, synset_dir)
        num_pairs = len(pairs_data)

        logger.debug( "Numero de pares : %d",  num_pairs)
        
        if num_pairs == 0:
            continue

        image_cache = {}

        logger.info( "carregando imagens...")
        valid_pairs = []
        
        for i, (image_filename_l, image_filename_r) in enumerate(pairs_data):        
            if image_filename_l not in image_cache:
                load_image_cache(image_cache, image_filename_l, VQA_DIR)
            if image_filename_r not in image_cache:        
                load_image_cache(image_cache, image_filename_r, IMAGENET_DIR)        
        
        logger.debug( "pronto")
        
        #acc,cm, y = predizer(model)

        test_pair_gen = pair_generator(pairs_data, image_cache, None, BATCH_SIZE)  
        #num_test_steps = len(pairs_data) // BATCH_SIZE                      
        
        logger.info("Predizendo similaridades...")
        tic()
        predicoes = predizer(model, generator=test_pair_gen, steps=num_pairs)
        logger.info("pronto")
        tac()
        
        print("Predicoes", len(predicoes))
        print("NUm pairs", num_pairs)
        print("Num steps ", BATCH_SIZE)

        sys.exit()

        for i in range(num_pairs-1):
            pairs_data[i].extend([predicoes[i]])
            similarities.append( pairs_data[i] )

            """if predicoes[i] == 1:
                pairs_data[i].extend([predicoes[i]])
                similarities.append( pairs_data[i] )
            """ 
        logger.info("Salvando as predicoes...")
        #predict_filename = "predicoes_{:s}.csv".format(vqa_file)
        predict_filename = "predicoes_distilation_1.csv"

        df = pd.DataFrame(similarities, columns=["mscoco", "imagenet", "similar"])
        df.to_csv(os.path.join(DATA_DIR, "predicoes", predict_filename), mode='a', header=0, index = 0, encoding="utf-8" )
        logger.info("salvo em %s", os.path.join(DATA_DIR, "predicoes" , predict_filename))

logger.info("Finalizado !!!")
