import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
#from glob import glob

st.title('Calculate integrals of shots')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='clinicalasamericas')

filenames = [file['Key'] for file in response.get('Contents', [])][1:]

#filenames = glob('lasamericas*.csv')

listnoultrafast = [i for i in filenames if 'ultrafast' not in i]

filename = st.selectbox('Select file to calculate integrals', listnoultrafast)

@st.cache_data
def read_dataframe(file):
    path = f's3://clinicalasamericas/{file}'
    df = pd.read_csv(path, skiprows = 4)
    #df = pd.read_csv(file, skiprows = 4)
    return df

df = read_dataframe(filename)

cutoff = st.selectbox('cut off', [0.5, 10, 20, 40, 100, 150], index = 3)

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
dfchz = df.loc[:, 'ch0':] - zeros
dfchz.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfchz], axis = 1)

ACR = st.number_input('ACR value', value = 0.951, format = '%.3f')
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
dfz['pulsetoplot'] = dfz.singlepulse * 1 

#Group by 300 ms
dfz['chunk'] = dfz.number // int(300000/750)
dfg = dfz.groupby('chunk').agg({'time':np.median, 'ch0z':np.sum, 'ch1z':np.sum})
dfg0 = dfg.loc[:,['time', 'ch0z']]
dfg0.columns = ['time', 'signal']
dfg0['ch'] = 'sensor'
dfg1 = dfg.loc[:,['time', 'ch1z']]
dfg1.columns = ['time', 'signal']
dfg1['ch'] = 'cerenkov'
dfgtp = pd.concat([dfg0, dfg1])
fig2 = px.line(dfgtp, x='time', y='signal', color = 'ch', markers = False)

for (n, (s, f)) in enumerate(zip(sts, fts)):
    fig2.add_vline(x=s, line_dash = 'dash', line_color = 'green', opacity = 0.5)
    fig2.add_vline(x=f, line_dash = 'dash', line_color = 'red', opacity = 0.5)
    dfz.loc[(dfz.time > s) & (dfz.time < f), 'shot'] = n

st.plotly_chart(fig2)

dfi = dfz.groupby('shot').agg({'sensorcharge':np.sum,
                                'cerenkovcharge':np.sum,
                                'dose':np.sum,
                                'singlepulse':np.sum})

st.dataframe(dfi)

pulseson = st.checkbox('See pulses (large files will make the app very slow)')

if pulseson:
    dfz0 = dfz.loc[:,['time', 'ch0z']]
    dfz0.columns = ['time', 'signal']
    dfz0['ch'] = 'sensor'
    dfz1 = dfz.loc[:, ['time', 'ch1z']]
    dfz1.columns = ['time', 'signal']
    dfz1['ch'] = 'cerenkov'
    dfz2 = dfz.loc[:, ['time', 'pulsetoplot']]
    dfz2.columns = ['time', 'signal']
    dfz2['ch'] = 'pulse'
    dfztp = pd.concat([dfz0, dfz1, dfz2])
    fig3 = px.line(dfztp, x='time', y='signal', color='ch', markers = True)

    for (n, (s, f)) in enumerate(zip(sts, fts)):
        fig3.add_vline(x=s, line_dash = 'dash', line_color = 'green', opacity = 0.5)
        fig3.add_vline(x=f, line_dash = 'dash', line_color = 'red', opacity = 0.5)
    st.plotly_chart(fig3)
