# -*- coding: utf-8 -*-


import copy
import keras

from keras.models import Sequential, Model
from keras.layers import Dense, Input, Flatten, Reshape, Lambda, concatenate, BatchNormalization, Conv2D, MaxPooling2D, Dropout
from keras import regularizers
from keras.initializers import RandomNormal

from keras.optimizers import Adam
import numpy as np
from keras import backend as K
from CustomLayers import MaskLayer, Max_S
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.externals import joblib
import tensorflow as tf
import os
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.use('Agg')

def AddNoise(input_args):
    x = input_args[0]
    noise = input_args[1]
    return x+noise



class SparseEstimatorNetwork():

    # def get_my_MSE_loss():
    #     def my_MSE(y_true, y_pred):
    #         return K.mean(K.square(y_pred - y_true))
    #     return my_MSE



    def __init__(self, img_shape=(28, 28), encoded_dim=2, Number_of_pilot=30,
                 regularizer_coef=1e-6 ,on_cloud=1, test_mode=0, log_path='.', normalize_mode=2, 
                 Noise_var_L=.01, Noise_var_H=.1, data_type=0, Enable_conv=0,Fixed_pilot=0,Enable_auto=1,Drou_out_sel=0):
        self.encoded_dim = encoded_dim
        self.optimizer = Adam(0.0001)
        self.img_shape = img_shape
        self.Number_of_pilot=Number_of_pilot
        self.regularizer_coef=regularizer_coef
        self.test_mode=test_mode        
        self.log_path=log_path        
        self.on_cloud=on_cloud
        self.normalize_mode=normalize_mode
        self.Noise_var_L=Noise_var_L
        self.Noise_var_H=Noise_var_H
        self.data_type=data_type
        self.Enable_conv=Enable_conv
        self.Fixed_pilot=Fixed_pilot
        self.Enable_auto=Enable_auto
        self.Drou_out_sel=Drou_out_sel
        if self.normalize_mode==2:
            self.scaler = {}
            self.scaler['min'] = 0
            self.scaler['max'] = 0
        self._initAndCompileFullModel(img_shape, encoded_dim)
        #self.scaler = StandardScaler(with_mean=True, with_std=True)
        
        
    def my_normalize(self,input_args):
        image = input_args
        min_v = -4# self.scaler['min']
        max_v = 4 #self.scaler['max']
        return (image - min_v) / (max_v - min_v)

    def my_denormalize(self,input_args):
        image = input_args
        min_v = -4 #self.scaler['min']
        max_v = 4 #self.scaler['max']
        return image*(max_v - min_v)+min_v   

    def _genSelectorModel(self, img_shape):
        selector = Sequential()
        selector.add(Flatten(input_shape=img_shape))
        #selector.add(Dense(img_shape[0]*img_shape[1], activation='relu'))
        if self.Fixed_pilot==1:
            selector.add(MaskLayer( input_dim=img_shape, output_dim=img_shape[0]*img_shape[1], 
                                     #kernel_regularizer= regularizers.l1(self.regularizer_coef), 
                                     #kernel_constraint= Max_S(Number_of_pilot=self.Number_of_pilot),
                                     Number_of_pilot=self.Number_of_pilot, Fixed=self.Fixed_pilot))
        elif self.Fixed_pilot==0:
            selector.add(MaskLayer( input_dim=img_shape, output_dim=img_shape[0]*img_shape[1], 
                                     kernel_regularizer= regularizers.l1(self.regularizer_coef), 
                                     kernel_constraint= Max_S(Number_of_pilot=self.Number_of_pilot),
                                     Number_of_pilot=self.Number_of_pilot, Fixed=self.Fixed_pilot))

        selector.summary()
        return selector

    def _genDropOutModel(self, img_shape):
        Sel_drop = Sequential()
        Sel_drop.add(Flatten(input_shape=img_shape))
        Sel_drop.add(Dropout(0.95))
        Sel_drop.summary()
        return Sel_drop

    def _genInterpolModel(self, img_shape):

        Interpol = Sequential()

        Interpol.add(Dense(1500, input_dim=img_shape+1, activation='relu'))
        #Interpol.add(Dense(1500, input_dim=img_shape+1, activation='relu'))
        #Interpol.add(Dense(img_shape, activation='relu'))
        Interpol.add(Dense(img_shape))

        Interpol.summary()
        return Interpol

    def _genConvModel(self, img_shape):
        initializer = 'he_normal'

        Conv = Sequential()
        #Conv.add(Conv2D(128, (32, 8), activation = 'relu', input_shape=img_shape ,kernel_initializer = initializer , padding='same'))
        Conv.add(Conv2D(128, (8, 4), activation = 'relu', input_shape=img_shape ,kernel_initializer = initializer , padding='same'))
        Conv.add(Conv2D(64, (4, 2), activation = 'relu', kernel_initializer = initializer , padding='same'))
        #Conv.add(Conv2D(32, (4, 2), activation = 'relu', kernel_initializer = initializer , padding='same'))

        #Conv.add(MaxPooling2D(pool_size=(4, 2)))
        #Conv.add(Dropout(0.1))
        
        #Conv.add(Conv2D(64, (4, 3), activation = 'relu', kernel_initializer = initializer , padding='same'))
        #Conv.add(MaxPooling2D(pool_size=(4, 2)))
        #Conv.add(Dropout(0.1))

        #Conv.add(Conv2D(1, (1, 1),  activation = 'relu', kernel_initializer = initializer , padding='same'))
        Conv.add(Conv2D(64, (1, 1), activation = 'relu', kernel_initializer = initializer , padding='same'))
        Conv.add(Conv2D(64, (4, 2), activation = 'relu', kernel_initializer = initializer , padding='same'))
        #Conv.add(Conv2D(1, (8, 4), activation = 'relu', kernel_initializer = initializer , padding='same'))
        Conv.add(Conv2D(1, (8, 4), kernel_initializer = initializer , padding='same'))
       
        Conv.summary()
        return Conv

    def _gensingle_reshpae_Model(self, input_dim,img_shape):

        single_reshape = Sequential()

        # #single_dense.add(Dense(np.prod(img_shape),input_shape=input_dim))
        single_reshape.add(Reshape(img_shape,input_shape=input_dim))

        single_reshape.summary()
        return single_reshape

    def _gensingledense_reshpae_Model(self, input_dim,img_shape,encoded_dim):

        single_dense = Sequential()

        # #single_dense.add(Dense(np.prod(img_shape),input_shape=input_dim))
        # single_dense.add(Reshape(img_shape,input_shape=input_dim))

        single_dense.add(Dense(1000,input_shape=input_dim))
        single_dense.add(Dense(600, activation='relu'))
        single_dense.add(Dense(encoded_dim, activation='relu'))
        single_dense.add(Dense(600, activation='relu'))
        single_dense.add(Dense(np.prod(img_shape)))
        single_dense.add(Reshape(img_shape))
    

        single_dense.summary()
        return single_dense


    def _genEncoderModel(self, encoded_dim,input_dim):
        """ Build Encoder Model Based on Paper Configuration
        Args:
            img_shape (tuple_) : shape of input image
            encoded_dim (int) : number of latent variables
        Return:
            A sequential keras model
                """

        encoder = Sequential()
        #encoder.add(Flatten(input_shape=img_shape))
        #encoder.add(Reshape(input_dim_t, input_shape=input_dim_t))

        # encoder.add(MaskLayer(input_shape=input_dim_t,output_dim=[input_dim_t], activation='linear', 
        #                            kernel_regularizer= regularizers.l1(self.regularizer_coef), 
        #                            kernel_constraint= Max_S(Number_of_pilot=self.Number_of_pilot),
        #                            Number_of_pilot=self.Number_of_pilot))
        # encoder.add(MaskLayer(input_dim=img_shape, activation='linear', 
        #                             kernel_regularizer= regularizers.l1(self.regularizer_coef), 
        #                             #kernel_regularizer= My_l1_reg, 
        #                             Number_of_pilot=self.Number_of_pilot))
        encoder.add(Dense(1000, input_shape=input_dim, activation='relu'))
        #encoder.add(Dropout(0.05))
        #encoder.add(Dense(500, input_shape=input_dim, activation='relu'))
        # encoder.add(Dropout(0.05))
        if self.Enable_conv==0:
            encoder.add(Dense(1000, activation='relu'))
        
        #encoder.add(Dense(1000, activation='relu'))
        #encoder.add(Dense(encoded_dim))
        encoder.add(Dense(encoded_dim, activation='relu'))
        #encoder.add(BatchNormalization())
        encoder.summary()
        return encoder

    def _getDecoderModel(self, encoded_dim, img_shape):
        """ Build Decoder Model Based on Paper Configuration
        Args:
            encoded_dim (int) : number of latent variables
            img_shape (tuple) : shape of target images
        Return:
            A sequential keras model
        """
        decoder = Sequential()
        #Conv.add(Dropout(0.1))
        decoder.add(Dense(1000, activation='relu', input_dim=encoded_dim+1))
        #decoder.add(Dense(1000, activation='relu', kernel_regularizer= regularizers.l1(0.00000002/1024)))
        if self.Enable_conv==0:
            decoder.add(Dense(1000, activation='relu')) 
        #decoder.add(Dense(1000, activation='relu')) 
        #decoder.add(Dense(1000, activation='relu')) 
        
        #decoder.add(Dense(np.prod(img_shape), activation='sigmoid'))
        decoder.add(Dense(np.prod(img_shape)))
        decoder.add(Reshape(img_shape))
        decoder.summary()
        return decoder
    

    def _initAndCompileFullModel(self, img_shape, encoded_dim):
        def my_MSE(y_true, y_pred):
            return K.mean(K.square(y_pred - y_true),axis=[-2,-1])

        if self.Drou_out_sel==0:
            self.selector= self._genSelectorModel (img_shape)
        elif self.Drou_out_sel==1:
            self.Drop_layer= self._genDropOutModel (img_shape)
        self.Interpol_m=self._genInterpolModel(img_shape[0]*img_shape[1])
        #self.Reshape_layer_t = self._gensingledense_reshpae_Model(input_dim=[img_shape[0]*img_shape[1]],img_shape=img_shape)

        if self.Enable_conv==1:
            self.conv_p= self._genConvModel ((*img_shape,1))
        if self.Enable_auto==1:
            self.encoder = self._genEncoderModel(encoded_dim, input_dim=[img_shape[0]*img_shape[1]+1])
            #self.encoder = self._genEncoderModel(encoded_dim, input_dim=[32*13])
            self.decoder = self._getDecoderModel(encoded_dim, img_shape)
        elif self.Enable_auto==0:
            self.Reshape_layer = self._gensingle_reshpae_Model(input_dim=[img_shape[0]*img_shape[1]],img_shape=img_shape)
            self.Dense_Reshape_layer = self._gensingledense_reshpae_Model(input_dim=[img_shape[0]*img_shape[1]],img_shape=img_shape,encoded_dim=self.encoded_dim)


        img = Input(shape=img_shape)
        noise = Input(shape=img_shape)
        variance = Input(shape=(1,))
        noisy_image = Lambda(AddNoise)([img, noise])

        # if self.normalize_mode==2:
        #     noisy_image_n = Lambda(self.my_normalize)(noisy_image)
        # else:
        #     noisy_image_n=noisy_image
        # selected_img= self.selector(noisy_image_n)
        
        if self.Drou_out_sel==0:
            selected_img= self.selector(noisy_image)
        elif self.Drou_out_sel==1:
            selected_img= self.Drop_layer(noisy_image)
        selected_img_concated = concatenate([selected_img, variance])
        Interpolated_img=self.Interpol_m(selected_img_concated)
        
        Interpolated_2D = self.Reshape_layer(Interpolated_img)


        print("the first stage")
        for layer in self.Interpol_m.layers:
            print(layer)
            layer.trainable = True
        for layer in self.conv_p.layers:
            print(layer)
            layer.trainable = False
        for layer in self.Dense_Reshape_layer.layers:
            print(layer)
            layer.trainable = False
        self.Dens_estim = Model([img, noise, variance], Interpolated_2D)
        self.Dens_estim.compile(optimizer=self.optimizer, loss='mse', metrics=['mse'])
        
        if self.Enable_conv==0:
            Conv_image_flatten=Interpolated_img
        else:
            
            Interpolated_image_2D=Reshape((*img_shape,1))(Interpolated_img)
            print(img_shape)
            print(Interpolated_image_2D.get_shape())
            Conv_image_2D=self.conv_p(Interpolated_image_2D)
            Conv_image_flatten=Flatten()(Conv_image_2D)


        if self.Enable_auto==1:
            input_concated = concatenate([Conv_image_flatten, variance])
         
            #concated = Concatenate([Flatten(input_shape=img_shape)(noisy_image), variance])
            encoded_repr = self.encoder(input_concated)

            concated = concatenate([encoded_repr, variance])
            gen_img = self.decoder(concated)

            # if self.normalize_mode==2:
            #     gen_img_s =gen_img # Lambda(self.my_denormalize)(gen_img)
            # else:
            #     gen_img_s=gen_img
            # self.autoencoder = Model([img, noise, variance], gen_img_s)

            self.autoencoder = Model([img, noise, variance], gen_img)

        elif self.Enable_auto==0:
            #input_concated = concatenate([Conv_image_flatten, variance])
            #input_concated=concatenate([Conv_image_flatten])

            gen_img_conv = self.Reshape_layer(Conv_image_flatten)
            gen_img = self.Dense_Reshape_layer(Conv_image_flatten)




            if self.Enable_conv==1:

                for layer in self.Interpol_m.layers:
                    print(layer)
                    layer.trainable = False
                for layer in self.conv_p.layers:
                    print(layer)
                    layer.trainable = True
                for layer in self.Dense_Reshape_layer.layers:
                    print(layer)
                    layer.trainable = False
                print("I am at conv")

                self.autoencoder_convonly = Model([img, noise, variance], gen_img_conv)
                self.autoencoder_convonly.compile(optimizer=self.optimizer, loss='mse',metrics=['mse'])



            for layer in self.Interpol_m.layers:
                print(layer)
                layer.trainable = False
            if self.Enable_conv==1:
                for layer in self.conv_p.layers:
                    print(layer)
                    layer.trainable = False
            for layer in self.Dense_Reshape_layer.layers:
                print(layer)
                layer.trainable = True
            print("i am at the last stage!")
            self.autoencoder = Model([img, noise, variance], gen_img)
            self.autoencoder.compile(optimizer=self.optimizer, loss='mse',metrics=['mse'])

            for layer in self.Interpol_m.layers:
                print(layer)
                layer.trainable = False
            if self.Enable_conv==1:
                for layer in self.conv_p.layers:
                    print(layer)
                    layer.trainable = True
            for layer in self.Dense_Reshape_layer.layers:
                print(layer)
                layer.trainable = True
            print("i am at the fine tune stage!")
            self.autoencoder_all = Model([img, noise, variance], gen_img)
            self.autoencoder_all.compile(optimizer=self.optimizer, loss='mse',metrics=['mse'])



        #self.autoencoder.compile(optimizer=self.optimizer, loss=my_MSE)
        #self.autoencoder.compile(optimizer=self.optimizer, loss='mse')
        #self.autoencoder.compile(optimizer=self.optimizer, loss='mae')
        
        if self.test_mode==1:
            if self.on_cloud==0:
                # if self.Enable_conv==1:
                #     Weigth_data_2=self.log_path+"/"+"weights_2.hdf5"
                #     if (os.path.isfile(Weigth_data_2)):
                #         print("Conv loaded")
                #         self.autoencoder_convonly.load_weights(Weigth_data_2)  
                Weigth_data=self.log_path+"/"+"weights.hdf5"
                if (os.path.isfile(Weigth_data)):
                    self.autoencoder.load_weights(Weigth_data)
                    print("loaded weights")
                else:
                    print("train the model first!!!")
                # Weigth_data_1=self.log_path+"/"+"weights_1.hdf5"
                # if (os.path.isfile(Weigth_data_1)):
                #     print("Dense loaded")
                #     self.Dens_estim.load_weights(Weigth_data_1) 
                if self.normalize_mode==2:
                    scaler_filename = self.log_path+"/"+"scaler.save"
                    print(scaler_filename)
                    if (os.path.isfile(scaler_filename)):
                        print("loaded scaleer")
                        self.scaler = joblib.load(scaler_filename)
                    else:
                        print("train the model first__!!!")
            else:
                #might be changed if the weights location changes
                Weigth_data=self.log_path+"/"+"weights.hdf5"
                if (os.path.isfile(Weigth_data)):
                    self.autoencoder.load_weights(Weigth_data)
                else:
                    print("train the model first!!!")
                if self.normalize_mode==2:
                    scaler_filename = self.log_path+"/"+"scaler.save"
                    if (os.path.isfile(scaler_filename)):
                        self.scaler = joblib.load(scaler_filename)
                    else:
                        print("train the model first__!!!")
    


    def train(self, x_in, y_in=[], batch_size=32, epochs=5):


        if self.data_type==0:

            Num_noise_per_image=1


            x_in= np.tile(x_in, (Num_noise_per_image,1,1))

            if self.normalize_mode==2:
                if self.data_type==0:
                    self.scaler['max'] = np.max(x_in)+.2
                    self.scaler['min'] = np.min(x_in)-.2
                    x_scaled=(x_in - (self.scaler['min']-10*self.Noise_var_L)) / (self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L))
                elif self.data_type==1:
                    self.scaler['max'] = np.max(x_in)+.2
                    self.scaler['min'] = np.min(x_in)-.2
                    x_scaled=(x_in - (self.scaler['min'])) / (self.scaler['max'] - (self.scaler['min']))

                print(self.scaler['max'] )
                print(self.scaler['min'] )

            else:
                x_scaled=x_in

            x_scaled_reshped =  x_scaled.reshape(x_in.shape)
            Weigth_data=self.log_path+"/"+"weights.hdf5"
            if (os.path.isfile(Weigth_data)):
                self.autoencoder.load_weights(Weigth_data)

            earlyStopping=keras.callbacks.EarlyStopping(monitor='val_loss', patience=2, verbose=0, mode='auto')

            noises = []
            variances = []

            for i in range(len(x_in)):
                var = np.random.uniform(self.Noise_var_L, self.Noise_var_H)
                noise = np.sqrt(var)/np.sqrt(2)*np.random.randn(*x_in[0].shape)
                if self.normalize_mode==4:
                    variances.append(25*var)
                elif self.normalize_mode==1:
                    noise=noise
                    #variances.append(np.log10(100*var)+1.5)
                    variances.append((np.log10(var*100)+2)/2)
                    #variances.append(0)
                elif self.normalize_mode==2:
                    noise=(noise) / (self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L))
                    if self.Noise_var_L==self.Noise_var_H:
                        variances.append(.1)
                    else:
                        variances.append((-np.log10(var)+np.log10(self.Noise_var_L))/(-np.log10(self.Noise_var_H)+np.log10(self.Noise_var_L)))

                elif self.normalize_mode==5:
                    noise=noise
                    #variances.append(np.log10(100*var)+1.5)
                    variances.append((-np.log10(var)+np.log10(self.Noise_var_L))*10)
                    #variances.append(0)
                else:
                    variances.append(var)

                noises.append(noise)

            noises = np.array(noises)
            variances = np.array(variances)

            if self.normalize_mode==2:
                scaler_filename = "/scaler.save"
                joblib.dump(self.scaler, self.log_path+scaler_filename)         


            self.Dens_estim.fit([x_scaled_reshped, noises, variances], x_scaled_reshped, epochs=epochs, batch_size=batch_size, shuffle=True,validation_split=0.15,
                                  callbacks=[earlyStopping,
                                            keras.callbacks.ModelCheckpoint(self.log_path+"/"+'weights_p.hdf5', 
                                               verbose=0, 
                                               monitor='val_loss',
                                               #save_best_only=False, 
                                               save_best_only=True, 
                                               save_weights_only=False, 
                                               mode='auto', 
                                               period=1)
                                            ])


            self.autoencoder.fit([x_scaled_reshped, noises, variances], x_scaled_reshped, epochs=epochs, batch_size=batch_size, shuffle=True,validation_split=0.15,
                                  callbacks=[earlyStopping,
                                            keras.callbacks.ModelCheckpoint(self.log_path+"/"+'weights.hdf5', 
                                               verbose=0, 
                                               monitor='val_loss',
                                               #save_best_only=False, 
                                               save_best_only=True, 
                                               save_weights_only=False, 
                                               mode='auto', 
                                               period=1)
                                            ])

        elif self.data_type==1 or  self.data_type==2:

            if self.normalize_mode==2:
                if self.data_type==0:
                    self.scaler['max'] = np.max(x_in)+.2
                    self.scaler['min'] = np.min(x_in)-.2
                    x_scaled=(x_in - (self.scaler['min']-10*self.Noise_var_L)) / (self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L))
                elif self.data_type==1 or self.data_type==2:
                    self.scaler['max'] = np.max(x_in)+.2
                    self.scaler['min'] = np.min(x_in)-.2
                    x_scaled=(x_in - (self.scaler['min'])) / (self.scaler['max'] - (self.scaler['min']))
                    y_scaled=(y_in - (self.scaler['min'])) / (self.scaler['max'] - (self.scaler['min']))
            else:
                x_scaled=x_in
                y_scaled=y_in


            print(self.scaler['max'] )
            print(self.scaler['min'] )

            x_scaled_reshped =  x_scaled.reshape(x_in.shape)
            y_scaled_reshped =  y_scaled.reshape(y_in.shape)
            
            

            noises = []
            variances = []
            if self.normalize_mode==1:
                var_v=((np.log10(self.Noise_var_L)+2)/2)
            elif self.normalize_mode==5:
                var_v=0
            elif self.normalize_mode==2:
                if self.Noise_var_L==self.Noise_var_H:
                    var_v=.1

            for i in range(len(x_in)):
                if self.normalize_mode==1:
                    noise = 0*np.random.randn(*x_in[0].shape)
                    #variances.append(np.log10(100*var)+1.5)
                    noises.append(noise)
                    variances.append(var_v)
                    #variances.append(0)
                elif self.normalize_mode==2:
                    noise = 0*np.random.randn(*x_in[0].shape)
                    noises.append(noise)
                    if self.Noise_var_L==self.Noise_var_H:
                        variances.append(var_v)
                    else:
                        error()
                elif self.normalize_mode==5:
                    noise = 0*np.random.randn(*x_in[0].shape)
                    #variances.append(np.log10(100*var)+1.5)
                    noises.append(noise)
                    variances.append(var_v)
                    #variances.append(0)
                else:
                    error()

            noises = np.array(noises)
            variances = np.array(variances)

            if self.normalize_mode==2:
                scaler_filename = "/scaler.save"
                joblib.dump(self.scaler, self.log_path+scaler_filename)         



            Weigth_data=self.log_path+"/"+"weights.hdf5"
            if (os.path.isfile(Weigth_data)):
                print("all loaded")
                self.autoencoder_all.load_weights(Weigth_data)

            # Weigth_data_3=self.log_path+"/"+"weights_3.hdf5"
            # if (os.path.isfile(Weigth_data_3)):
            #     print("all loaded")
            #     self.autoencoder.load_weights(Weigth_data_3)

            # Weigth_data_2=self.log_path+"/"+"weights_2.hdf5"
            # if (os.path.isfile(Weigth_data_2)):
            #     print("Conv loaded")
            #     self.autoencoder_convonly.load_weights(Weigth_data_2)

            # Weigth_data_1=self.log_path+"/"+"weights_1.hdf5"
            # if (os.path.isfile(Weigth_data_1)):
            #     print("Dense loaded")
            #     self.Dens_estim.load_weights(Weigth_data_1)

            # earlyStopping_1=keras.callbacks.EarlyStopping(monitor='val_loss', patience=2, verbose=0, mode='auto')
            # self.Dens_estim.fit([x_scaled_reshped, noises, variances], y_scaled_reshped, epochs=epochs, batch_size=batch_size, shuffle=True,validation_split=0.15,
            #                       callbacks=[earlyStopping_1,
            #                                 keras.callbacks.ModelCheckpoint(self.log_path+"/"+'weights_1.hdf5', 
            #                                    verbose=0, 
            #                                    monitor='val_loss',
            #                                    #save_best_only=False, 
            #                                    save_best_only=True, 
            #                                    save_weights_only=False, 
            #                                    mode='auto', 
            #                                    period=1)
            #                                 ])

            # if self.Enable_conv==1:

            #     earlyStopping_2=keras.callbacks.EarlyStopping(monitor='val_loss', patience=2, verbose=0, mode='auto')
            #     self.autoencoder_convonly.fit([x_scaled_reshped, noises, variances], y_scaled_reshped, epochs=epochs, batch_size=batch_size, shuffle=True,validation_split=0.15,
            #                           callbacks=[earlyStopping_2,
            #                                     keras.callbacks.ModelCheckpoint(self.log_path+"/"+'weights_2.hdf5', 
            #                                        verbose=0, 
            #                                        monitor='val_loss',
            #                                        #save_best_only=False, 
            #                                        save_best_only=True, 
            #                                        save_weights_only=False, 
            #                                        mode='auto', 
            #                                        period=1)
            #                                     ])


            # earlyStopping_e=keras.callbacks.EarlyStopping(monitor='val_loss', patience=2, verbose=0, mode='auto')
            # self.autoencoder.fit([x_scaled_reshped, noises, variances], y_scaled_reshped, epochs=epochs, batch_size=batch_size, shuffle=True,validation_split=0.15,
            #                       callbacks=[earlyStopping_e,
            #                                 keras.callbacks.ModelCheckpoint(self.log_path+"/"+'weights_3.hdf5', 
            #                                    verbose=0, 
            #                                    monitor='val_loss',
            #                                    #save_best_only=False, 
            #                                    save_best_only=True, 
            #                                    save_weights_only=False, 
            #                                    mode='auto', 
            #                                    period=1)
            #                                 ])

            earlyStopping_e=keras.callbacks.EarlyStopping(monitor='val_loss', patience=3, verbose=0, mode='auto')
            self.autoencoder_all.fit([x_scaled_reshped, noises, variances], y_scaled_reshped, epochs=epochs, batch_size=batch_size, shuffle=True,validation_split=0.3,
                                  callbacks=[earlyStopping_e,
                                            keras.callbacks.ModelCheckpoint(self.log_path+"/"+'weights.hdf5', 
                                               verbose=0, 
                                               monitor='val_loss',
                                               #save_best_only=False, 
                                               save_best_only=True, 
                                               save_weights_only=False, 
                                               mode='auto', 
                                               period=1)
                                            ])

    def test(self, x_in, var):

        #print(self.scaler['max'] )
        #print(self.scaler['min'] )

        if self.normalize_mode==2:
            if self.data_type==0:
                #x_scaled = self.scaler.transform(x_in.reshape(len(x_in),-1))
                x_scaled=(x_in - (self.scaler['min']-10*self.Noise_var_L)) / (self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L))
            elif self.data_type==1 or self.data_type==2:
                x_scaled=(x_in - (self.scaler['min'])) / (self.scaler['max'] - (self.scaler['min']))
        else:
            x_scaled = x_in

        x_scaled_reshped =  x_scaled.reshape(x_in.shape)
        y = self.autoencoder.predict([x_scaled_reshped.reshape(*x_in.shape),np.zeros(x_in.shape), var*np.ones((len(x_in), 1))])
        y_intrpolated = self.Dens_estim.predict([x_scaled_reshped.reshape(*x_in.shape),np.zeros(x_in.shape), var*np.ones((len(x_in), 1))])
        y_ConvOut = self.autoencoder_convonly.predict([x_scaled_reshped.reshape(*x_in.shape),np.zeros(x_in.shape), var*np.ones((len(x_in), 1))])

        if self.normalize_mode==2:
            #y_true = self.scaler.inverse_transform(y.reshape(len(y),-1))
            if self.data_type==0:
                y_true = y*(self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L)) + (self.scaler['min']-10*self.Noise_var_L)
                y_intrpolated_true = y_intrpolated*(self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L)) + (self.scaler['min']-10*self.Noise_var_L)
                y_ConvOut_true = y_ConvOut*(self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L)) + (self.scaler['min']-10*self.Noise_var_L)
            elif self.data_type==1 or  self.data_type==2:
                y_true = y*(self.scaler['max'] - (self.scaler['min'])) + (self.scaler['min'])
                y_intrpolated_true = y_intrpolated*(self.scaler['max'] - (self.scaler['min'])) + (self.scaler['min'])
                y_ConvOut_true = y_ConvOut*(self.scaler['max'] - (self.scaler['min'])) + (self.scaler['min'])
        else:
            y_true=y

        return y_true.reshape(*x_in.shape),y_intrpolated_true,y_ConvOut_true
        

    # def FindEstiamte(self, x_test, fileName="test.png"):
    #     #fig = plt.figure(figsize=[20, 20/3])
    #     x_in = x_test
    #     y = self.test(x_in.reshape(1,x_in.shape[0],x_in.shape[1]))

    #     fig = plt.figure(figsize=[20, 20/2])
    #     i=0
    #     ax = fig.add_subplot(1, 2, i*2+1)
    #     ax.set_axis_off()
    #     ax.imshow(x_in)
    #     ax = fig.add_subplot(1, 2, i*2+2)
    #     ax.set_axis_off()
    #     ax.imshow(y[0]) #Layer cut
    #     fig.savefig(fileName)
    #     return y

    def generateAndPlot(self, x_test, y_test=[], n = 10, fileName="generated.png"):
        if self.data_type==0:
            Sampled_image_model = K.function([self.selector.layers[0].input],
                                      [self.selector.layers[1].output])

            #Sampled_interpoled_model = K.function([self.Interpol_m.layers[0].input],
            #                          [self.Interpol_m.layers[0].output])

            nb_of_plots=3
            fig = plt.figure(figsize=[20, 20*n/nb_of_plots])
            Test_error=np.array(np.zeros(shape=(1,n)))
            Test_error_int=np.array(np.zeros(shape=(1,n)))
            Test_error_conv=np.array(np.zeros(shape=(1,n)))
            Y_all=[]
            X_all=[]
        
            if self.normalize_mode==2:
                var_v=.1
            else:
                var_v=0


            for i in range(n):
                x_in = x_test[np.random.randint(len(x_test))]
                x=copy.copy(x_in)
                y = self.test(x.reshape(1,x_test.shape[1],x_test.shape[2]),var_v)
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+1)
                ax.set_axis_off()
                ax.imshow(x)
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+2)
                ax.set_axis_off()
                ax.imshow(y[0]) #Layer cut

                if self.normalize_mode==2:
                    #x_scaled = self.scaler.transform(x_in.reshape(len(x_in),-1))
                    x_n=(x - (self.scaler['min']-10*self.Noise_var_L)) / (self.scaler['max'] - (self.scaler['min']-10*self.Noise_var_L))
                
                Sampled_image = Sampled_image_model([x_n.reshape(1,x_test.shape[1],x_test.shape[2])])[0]
                #Sampled_image[Sampled_image<1e-6]=0
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+3)
                ax.set_axis_off()
                ax.imshow(Sampled_image.reshape(x_test.shape[1],x_test.shape[2]))
                
                # selected_img_concated = concatenate([selected_img, variance])

                # Interpolated_image = Sampled_interpoled_model([Sampled_image, 0.1])[0]
                # ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+4)
                # ax.set_axis_off()
                # ax.imshow(Interpolated_image.reshape(x_test.shape[1],x_test.shape[2]))
   

                Test_error[0,i]=np.mean(np.square(x-y[0]))
                X_all.append(x)
                Y_all.append(y[0])




            fig.savefig(fileName)
            return Test_error, Y_all, X_all
        elif self.data_type==1 or self.data_type==2:
            Sampled_image_model = K.function([self.selector.layers[0].input],
                                      [self.selector.layers[1].output])

            Interpolated_image_model = K.function([self.selector.layers[0].input],
                                      [self.Interpol_m.layers[1].output])

            nb_of_plots=5

            fig = plt.figure(figsize=[20, 20*n/nb_of_plots])
            Test_error=np.array(np.zeros(shape=(1,n)))
            Test_error_int=np.array(np.zeros(shape=(1,n)))
            Test_error_conv=np.array(np.zeros(shape=(1,n)))
            Y_all=[]
            X_all=[]
            if self.normalize_mode==2:
                var_v=.1
            else:
                var_v=0

            for i in range(n):
                t_idx=np.random.randint(len(x_test))
                x_in = x_test[t_idx]
                Y_in = y_test[t_idx]
                x=copy.copy(x_in)
                y, y_intrpolated,y_ConvOut= self.test(x.reshape(1,x_test.shape[1],x_test.shape[2]),var_v)
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+1)
                ax.set_axis_off()
                ax.imshow(x)
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+2)
                ax.set_axis_off()
                ax.imshow(y[0]) #Layer cut
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+3)
                ax.set_axis_off()
                ax.imshow(Y_in) #Layer cut
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+4)
                ax.set_axis_off()
                ax.imshow(y_intrpolated[0]) #Layer cut
                                
                if self.normalize_mode==2:
                    #x_scaled = self.scaler.transform(x_in.reshape(len(x_in),-1))
                    x_n=(x - (self.scaler['min'])) / (self.scaler['max'] - (self.scaler['min']))
                
                Sampled_image = Sampled_image_model([x_n.reshape(1,x_test.shape[1],x_test.shape[2])])[0]
                #Sampled_image[Sampled_image<1e-6]=0
                ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+5)
                ax.set_axis_off()
                ax.imshow(Sampled_image.reshape(x_test.shape[1],x_test.shape[2]))

                # Interpolated_image = Interpolated_image_model([x_n.reshape(1,x_test.shape[1],x_test.shape[2]), var_v])[0]
                # #Sampled_image[Sampled_image<1e-6]=0
                # ax = fig.add_subplot(n, nb_of_plots, i*nb_of_plots+5)
                # ax.set_axis_off()
                # ax.imshow(Interpolated_image.reshape(x_test.shape[1],x_test.shape[2]))

                Test_error[0,i]=np.mean(np.square(Y_in-y[0]))
                Test_error_int[0,i]=np.mean(np.square(Y_in-y_intrpolated[0]))
                #Test_error_conv[0,i]=np.mean(np.square(Y_in-y[0]))
                X_all.append(x)
                Y_all.append(y[0])

            fig.savefig(fileName)
            return Test_error,Test_error_int, Y_all, X_all

        
# if __name__=='__main__':
#     # here is to just test the network
#     from keras.datasets import mnist
#     (x_train, y_train), (x_test, y_test) = mnist.load_data()
#     x_train = x_train.astype(np.float32) / 255.
#     x_test = x_test.astype(np.float32) / 255.
#     network = SparseEstimatorNetwork(encoded_dim=10)
#     network.train(x_train, epochs=1, a=.1, b=1)
#     #y = network.test(x_test[0:10])
#     network.generateAndPlot(x_test)
