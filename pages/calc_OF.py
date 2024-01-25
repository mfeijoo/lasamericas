import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
#from glob import glob

st.title('Calculate OF')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='clinicalasamericas')

filenames = [file['Key'] for file in response.get('Contents', [])][1:]

#filenames = glob('lasamericas*.csv')

listnoultrafast = [i for i in filenames if 'ultrafast' not in i]

filenames = st.multiselect('Select files to calculate OF', listnoultrafast)

@st.cache_data
def read_dataframes(files):
    dfs = []
    for file in files:
        path = f's3://clinicalasamericas/{file}'
        df = pd.read_csv(path, skiprows = 4)
        #df = pd.read_csv(file, skiprows = 4)
        dfs.append(df)
    return dfs

dfs = read_dataframes(filenames)

cutoff = st.selectbox('cut off', [0.5, 10, 20, 40, 100, 150], index = 3)

ACR = st.number_input('ACR value', value = 0.9419, format = '%.4f')

dfis = []
for df in dfs:
    last_time = df.iloc[-1,1]
    zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
    dfchz = df.loc[:, 'ch0':] - zeros
    dfchz.columns = ['ch0z', 'ch1z']
    dfz = pd.concat([df, dfchz], axis = 1)

    dfz['sensorcharge'] = dfz.ch0z * 0.03
    dfz['cerenkovcharge'] = dfz.ch1z * 0.03
    dfz['dose'] = dfz.sensorcharge - dfz.cerenkovcharge * ACR

    dfz['chunk'] = dfz.number // (300000/700)
    group = dfz.groupby('chunk')
    dfg = group.agg({'time':np.median,
                    'ch0z':np.sum,
                    'ch1z':np.sum})
    dfg['time_min'] = group['time'].min()
    dfg['time_max'] = group['time'].max()
    dfg['ch0diff'] = dfg.ch0z.diff()
    starttimes = dfg.loc[dfg.ch0diff > cutoff, 'time_min']
    finishtimes = dfg.loc[dfg.ch0diff < -cutoff, 'time_max']
    stss = [starttimes.iloc[0]] + list(starttimes[starttimes.diff()>2])
    sts = [t - 0.04 for t in stss]
    ftss = [finishtimes.iloc[0]] + list(finishtimes[finishtimes.diff()>2])
    fts = [t + 0.04 for t in ftss]

    #Find pulses
    maxvaluech = dfz.loc[(dfz.time < sts[0] - 1) | (dfz.time > fts[-1] + 1), 'ch0z'].max()
    dfz['pulse'] = dfz.ch0z > maxvaluech * 1.05
    dfz.loc[dfz.pulse, 'pulsenum'] = 1
    dfz.fillna({'pulsenum':0}, inplace = True)
    dfz['pulsecoincide'] = dfz.loc[dfz.pulse, 'number'].diff() == 1
    dfz.fillna({'pulsecoincide':False}, inplace = True)
    dfz['singlepulse'] = dfz.pulse & ~dfz.pulsecoincide

    for (n, (s, f)) in enumerate(zip(sts, fts)):
        dfz.loc[(dfz.time > s) & (dfz.time < f), 'shot'] = n


    dfi = dfz.groupby('shot').agg({'sensorcharge':np.sum,
                                'cerenkovcharge':np.sum,
                                'dose':np.sum,
                                'singlepulse':np.sum})
    dfis.append(dfi)

dfit = pd.concat(dfis)
st.dataframe(dfit)

fsizes = st.text_input('select field sizes (cm) separated by commas',
        value = '1,1,1,10,10,8,8,6,6,5,5,4,4,3,3,10,10')
listsizes = fsizes.split(',')
sizesint = [float(i) for i in listsizes]
if len(sizesint) != len(dfit):
    st.error('Wrong number of field sizes')
dfit['field'] = sizesint
dfit['OF'] = dfit.dose / dfit.loc[dfit.field == 10, 'dose'].mean()
of = dfit.groupby('field').mean()
of['error'] = dfit.groupby('field').std()['OF']
of.reset_index(inplace = True)
fig1 = px.scatter(of, x='field', y='OF', error_y='error')
st.plotly_chart(fig1)
st.dataframe(of.loc[:,['field', 'dose',  'OF', 'error']])

