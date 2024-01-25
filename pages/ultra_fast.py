import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import boto3
#from glob import glob

st.title('Ultra Fast Analysis')

s3 = boto3.client('s3')

response = s3.list_objects_v2(Bucket='clinicalasamericas')

filenames = [file['Key'] for file in response.get('Contents', [])][1:]

#filenames = glob('lasamericas*.csv')

listoffiles = [file for file in filenames if 'ultrafast' in file]

filenow = st.selectbox('Select file to analyze:', listoffiles)

@st.cache_data
def read_dataframe(file):
    path = f's3://clinicalasamericas/{file}'
    df = pd.read_csv(path, skiprows = 4)
    #df = pd.read_csv(file, skiprows = 4)
    return df

df = read_dataframe(filenow)

showdataframe = st.checkbox('Show dataframe')

if showdataframe:
    st.dataframe(df)

#Prepare data frame to first plot

last_time = df.iloc[-1,1]
zeros = df.loc[(df.time < 1) | (df.time > last_time - 1), 'ch0':].mean()
dfzeros = df.loc[:, 'ch0':] - zeros
dfzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfzeros], axis = 1)

df0 = dfz.loc[:,['time', 'ch0z']]
df0.columns = ['time', 'voltage']
df0['ch'] = 'sensor'
df1 = dfz.loc[:, ['time', 'ch1z']]
df1.columns = ['time', 'voltage']
df1['ch'] = 'cerenkov'
dftp = pd.concat([df0, df1])

@st.cache_data
def plotfigch(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string, color='ch')
    return fig

@st.cache_data
def plotfig(df, x_string = 'time', y_string = 'voltage'):
    fig = px.scatter(df, x= x_string, y = y_string)
    return fig

fig1 = plotfigch(dftp)

st.plotly_chart(fig1)

group = st.checkbox('group every 300 ms')
if group:
    dfz['chunk'] = dfz.number // int(300000/750)
    dfg = dfz.groupby('chunk').agg({'time':np.median, 'ch0z':np.sum, 'ch1z':np.sum})
    dfg0 = dfg.loc[:,['time', 'ch0z']]
    dfg0.columns = ['time', 'signal']
    dfg0['ch'] = 'sensor'
    dfg1 = dfg.loc[:,['time', 'ch1z']]
    dfg1.columns = ['time', 'signal']
    dfg1['ch'] = 'cerenkov'
    dfgtp = pd.concat([dfg0, dfg1])
    fig1b = px.line(dfgtp, x='time', y='signal', color = 'ch', markers = False)
    st.plotly_chart(fig1b)

t0 = st.number_input('time before beam on', min_value=0.0, max_value=df.time.round(1).max())
t1 = st.number_input('time after beam off', min_value=0.0, max_value=df.time.round(1).max())
t2 = st.number_input('time begining of PDD', min_value=0.0, max_value=df.time.round(1).max())
t3 = st.number_input('time end of PDD', min_value=0.0, max_value=df.time.round(1).max())
depth = st.number_input('PDD depth (mm)', min_value=0, value = 130)
t4 = st.number_input('time begining of profile', min_value=0.0, max_value=df.time.round(1).max())
t5 = st.number_input('time end  of profile', min_value=0.0, max_value=df.time.round(1).max())
pulsesthreshold = st.slider('Chose threshold for pulses', min_value = 1, max_value = 20, value = 5)
ACR = st.number_input('ACR', value = 0.94)

#calculate zeros
nzeros = df.loc[(df.time < t0) | (df.time > t1), 'ch0':].mean()
dfnzeros = df.loc[:, ['ch0', 'ch1']] - nzeros
dfnzeros.columns = ['ch0z', 'ch1z']
dfz = pd.concat([df, dfnzeros], axis=1)
#prepare to plot zeros
df0z = dfz.loc[:, ['time', 'ch0z']]
df0z.columns = ['time', 'voltage']
df0z['ch'] = 'sensor'
df1z = dfz.loc[:, ['time', 'ch1z']]
df1z.columns = ['time', 'voltage']
df1z['ch'] = 'cerenkov'
dftpz = pd.concat([df0z, df1z])
#plot zeros
fig2 = plotfigch(dftpz)
fig2.add_vline(x=t0, line_dash = 'dash', line_color = 'green', opacity = 0.5)
fig2.add_vline(x=t1, line_dash = 'dash', line_color = 'red', opacity = 0.5)
fig2.add_vrect(x0 = t2, x1 = t3, line_width = 0, fillcolor = 'red', opacity = 0.2)
fig2.add_vrect(x0 = t4, x1 = t5, line_width = 0, fillcolor = 'green', opacity = 0.2)
st.plotly_chart(fig2)
#find pulses
maxzeros = dfz.loc[(dfz.time < t0) | (dfz.time > t1), 'ch0z'].max()
dfz['pulse'] = (dfz.ch0z > maxzeros * (1 + pulsesthreshold / 100))
#find coincide pulses
dfz['pulseafter'] = dfz.pulse.shift(-1)
dfz['pulsecoincide'] = dfz.pulse + dfz.pulseafter == 2
dfz['singlepulse'] = dfz.pulse
dfz['pulsecoincideafter'] = dfz.pulsecoincide.shift()
dfz.dropna(inplace = True)
dfz.loc[dfz.pulsecoincideafter, 'singlepulse'] = False
numberofpulses = dfz[(dfz.time > t2) & (dfz.time < t3)].pulse.sum()
numberofpulsescoincide = dfz[(dfz.time > t2) & (dfz.time < t3)].pulsecoincide.sum()
numberofsinglepulses = dfz[(dfz.time > t2) & (dfz.time < t3)].singlepulse.sum()
st.write(f'Number of pulses: {numberofpulses}')
st.write(f'Number of pulses coinciding: {numberofpulsescoincide}')
st.write(f'Number of single pulses: {numberofsinglepulses}')
#find complete dose of pulse and pulseafter
dfz['chargesensor'] = dfz.ch0z * 0.03
dfz['chargecerenkov'] = dfz.ch1z * 0.03
dfz['dose'] = dfz.chargesensor - dfz.chargecerenkov * ACR
dfz['doseafter'] = 0
dfz.loc[dfz.pulsecoincideafter, 'doseafter'] = dfz.dose
dfz['completedose'] = dfz.dose + dfz.doseafter.shift(-1)
dfz.loc[dfz.pulsecoincideafter, 'completedose'] = 0

#dfztoplot = dfz[(dfz.time > t2) & (dfz.time < t3)]
#fig3 = plotfig(dfztoplot,  x_string = 'time', y_string = 'completedose')
#st.plotly_chart(fig3)
#mindose1 = st.number_input('PDD dose threshold (0.0xx)', value=20)
#mindose = mindose1 / 1000

#calculate PDD
#dfzpdd = dfz[((dfz.time > t2) & (dfz.time < t3)) & (dfz.completedose > mindose)]

softmaxpdd = st.slider('soft value to calculate pdd maximum', min_value=0.9, max_value =1.0, value=0.95)
dfzpdd = dfz[(dfz.time > t2) & (dfz.time < t3)]
dfzpdd['reldose'] = dfzpdd.completedose / (dfzpdd.completedose.max() * softmaxpdd) * 100
realvel = depth / (t3 - t2)
st.write('Speed measured: %.2f mm/s' %realvel)
dfzpdd['disttraveled'] = dfzpdd.time.diff() * realvel
dfzpdd['pos1'] = dfzpdd.disttraveled.cumsum()
dfzpdd['pos'] = depth - dfzpdd.pos1 
fig4 = plotfig(dfzpdd, x_string ='pos', y_string ='completedose')
fig4 = go.Figure()
pddpulses = go.Scatter(
        x = dfzpdd.pos,
        y = dfzpdd.reldose,
        mode = 'markers',
        name = 'pulses',
        marker = dict(size = 3, color = 'blue', opacity = 0.5),
        )
fig4.add_trace(pddpulses)

#Soft PDD
dfzallpdd = dfz[(dfz.time > t2) & (dfz.time < t3)]
numberofsamples = len(dfzallpdd)
samplespermm = numberofsamples / depth
st.write('Number of samples per mm: %s' %int(samplespermm))
numberofpulses = dfzpdd.singlepulse.sum()
pulsespermm = numberofpulses / depth
st.write('Number of pulses per mm: %s' %int(pulsespermm))
softvalue = st.slider('Rolling sum value', min_value = 0, value = 500, max_value = 1000)
dfzpdd['softdose'] = dfzpdd.completedose.rolling(softvalue, center = True).sum()
dfzpdd['dosepercent'] = dfzpdd.softdose / dfzpdd.softdose.max() * 100
pddsoft = go.Scatter(
        x = dfzpdd.pos,
        y = dfzpdd.dosepercent,
        mode = 'lines',
        name = 'PDD soft',
        line = go.scatter.Line(color = 'red')
        )
fig4.add_trace(pddsoft)

st.plotly_chart(fig4)

showpdddata = st.checkbox('Show PDD data')
if showpdddata:
    st.dataframe(dfzpdd.loc[:,['completedose', 'softdose', 'dosepercent', 'pos']])


#Calculate profile
dfzprofile = dfz.loc[(dfz.time > t4) & (dfz.time < t5)]
#fig6 = plotfig(dfzprofile, x_string = 'time', y_string = 'completedose')
#st.plotly_chart(fig6)
profilespeed = st.number_input('estimated motor speed', min_value = 8.00, max_value = 30.00, value = 9.26)
softmaxprofile = st.slider('soft value to calculate pdd maximum', min_value=0.9, max_value =1.0, value=0.90)
dfzprofile['disttraveled'] = dfzprofile.time.diff() * profilespeed
dfzprofile['pos1'] = dfzprofile.disttraveled.cumsum()
centerprofile = dfzprofile.loc[dfzprofile.completedose >= dfzprofile.completedose.max() * softmaxprofile, 'pos1'].median()
avmaxdose = dfzprofile.loc[dfzprofile.completedose >= dfzprofile.completedose.max() * softmaxprofile, 'completedose'].mean()
dfzprofile['reldose'] = dfzprofile.completedose / avmaxdose * 100
dfzprofile['pos'] = dfzprofile.pos1 - centerprofile
fig7 = go.Figure()
fig7.add_trace(
        go.Scatter(
            x = dfzprofile.pos,
            y = dfzprofile.reldose,
            name = 'pulses',
            mode = 'markers',
            marker = dict(size = 3, color = 'blue', opacity = 0.5),
            )
        )

#profilemindose1 = st.number_input('Profile dose threshold (0.00xx)', value = 60)
#profilemindose = profilemindose1 / 10000
profilesoft = st.slider('Soft value for profile', min_value =0, max_value =1000, value = 500)
#dfzgp = dfzprofile[dfzprofile.completedose > profilemindose]
dfzgp = dfzprofile
dfzgp['dosesoft'] = dfzgp.completedose.rolling(profilesoft, center = True).sum()
dfzgp['dosepercent'] = dfzgp.dosesoft / dfzgp.dosesoft.max() * 100
fig7.add_trace(
        go.Scatter(
            x=dfzgp.pos,
            y=dfzgp.dosepercent,
            mode = "lines",
            line = go.scatter.Line(color = 'red'),
            name = 'soft profile',
            showlegend=True)
        )
            
fig7.add_vline(x = 0, line_color = 'black', line_dash = 'dash')
# Calculate field size
edge1 = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.reldose > 50), 'pos'].max()
fig7.add_vline(x = edge1, line_color = 'green', line_dash = 'dash')
edge2 = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.reldose > 50), 'pos'].min()
fig7.add_vline(x = edge2, line_color = 'green', line_dash = 'dash')
fieldsize = edge1 - edge2
fig7.add_annotation(
        x = -1,
        y = 50,
        text = 'Size: %.2f mm' %fieldsize,
        font = dict(size = 11, color = 'red'),
        showarrow = False
        )

#calculate penumbra
penumbraright1 = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.reldose > 80), 'pos'].max()
penumbraright2 = dfzprofile.loc[(dfzprofile.pos > 0) & (dfzprofile.reldose > 20), 'pos'].max()
penumbraleft1 = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.reldose > 80), 'pos'].min()
penumbraleft2 = dfzprofile.loc[(dfzprofile.pos < 0) & (dfzprofile.reldose > 20), 'pos'].min()
fig7.add_vrect(x0 = penumbraright1, x1 = penumbraright2, line_width = 0, fillcolor = 'orange', opacity = 0.5)
fig7.add_vrect(x0 = penumbraleft2, x1 = penumbraleft1, line_width = 0, fillcolor = 'orange', opacity = 0.5)

penumbraright = penumbraright2 - penumbraright1
penumbraleft = penumbraleft1 - penumbraleft2

fig7.add_annotation(
        x = penumbraright2 + 5,
        y = 50,
        text = 'P.: %.2f mm' %penumbraright,
        font = dict(size = 11, color = 'green'),
        showarrow = False)
fig7.add_annotation(
        x = penumbraleft2 - 5,
        y = 50,
        text = 'P.: %.2f mm' %penumbraleft,
        font = dict(size = 11, color = 'magenta'),
        showarrow = False)


st.plotly_chart(fig7)
showprofiledata = st.checkbox('Show Profile data')
if showprofiledata:
    st.dataframe(dfzprofile.loc[:,['pos', 'completedose', 'dosesoft', 'dosepercent', 'reldose']]) 
