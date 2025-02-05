# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 23:17:56 2024

@author: yone
"""


import numpy as np
import pandas as pd
import streamlit as st
import os
import pydeck as pdk

try:
    print('doing')
    path = os.path.dirname(os.path.abspath(__file__))+"\\"
except:
    print("skip")
    path = os.getcwd()+"\\"
print("Hello!!!!")
print(path)

###ファイルパス設定（直下またはgithubのURL参照）
#path = 'C:/Users/yone/Documents/PythonScripts/g_finder/'
#path = 'https://github.com/yoneshin357/g_finder/blob/main/'
#path = 'https://github.com/yoneshin357/g_finder/raw/refs/heads/main/'
path= ''

###CSVデータを読み込む
kilo = pd.read_csv(path+"tizukiro.csv", encoding="shift_jis")
sta = pd.read_csv(path+"station_jre.csv", encoding="shift_jis")
data = pd.read_csv(path+"karasuyama.csv", encoding="shift_jis")

#不要
#,encoding='cp932



print("行、列=",data.shape)


# Streamlitアプリの設定
st.set_page_config(page_title="Green Finder", 
                   layout="wide", page_icon="🌳",
                   initial_sidebar_state="expanded")
#st.write("path="+str(path))

limit_dmy =  pd.DataFrame({"閾値": pd.Series([400, 200, 50, 50, 200])})
limit =  pd.DataFrame({"閾値": pd.Series([0, 0, 0, 0, 0])})
limit.index=["側方上部","側方上部(窓部)","下部","側方下部","上部"]
limit_dmy.index=["側方上部","側方上部(窓部)","下部","側方下部","上部"]
limit_dict = limit.to_dict(orient='dict')['閾値']

data['lim'] = data['支障位置'].map(limit_dict)

data['judge'] = (data['支障量'] >= data['lim']).astype(int)
for position in limit_dict.keys():
    data[f'判定_{position}'] = ((data['judge'] == 1) & (data['支障位置'] == position)).astype(int)


data['date'] = pd.to_datetime(data['測定日']).dt.date

intvl = 200
data['集計キロ程'] = data['キロ程']//intvl*intvl+int(intvl/2)

tmp = data.groupby(['通称線','走行方向','date','集計キロ程'])[['judge','判定_側方上部','判定_側方上部(窓部)','判定_下部','判定_側方下部','判定_上部']].sum().reset_index()
tmp2 = tmp.merge(kilo[['線名','キロ程','経度','緯度']],left_on=['集計キロ程','通称線'],right_on=['キロ程','線名'])
tmp2 = tmp2.rename(columns={'経度': 'lon', '緯度': 'lat'})

tsusho_choice = data['通称線'].unique()
dir_choice = data['走行方向'].unique()
date_choice = data['date'].unique()
obj_choice =data['ビデオ確認による対象物'].unique()
keito_choice =data['支障物確認を行う担当分野'].unique()

with st.sidebar.form(key="my_form"):
    st.write('データインポート')
    uploaded_file = st.file_uploader('ファイルアップロード', type=['csv'])
    if uploaded_file is not None:
        st.write('アップロードされたファイル:', uploaded_file.name)
        content = uploaded_file.read()
    selectbox_state = st.selectbox("線区", tsusho_choice)
    selectbox_direction = st.selectbox("走行方向", dir_choice)
    numberinput_threshold = st.number_input("集計間隔[m]", value=200, min_value=100, max_value=1000, step=1, format="%i")
    st.write('支障カウント閾値')
    edited_limit = st.data_editor(limit_dmy)
    pressed = st.form_submit_button("マップ更新")

expander = st.sidebar.expander("Help")
expander.write(
    """
    This app allows users to view migration between states from 2018-2019.
    Overall US plots all states with substantial migration-based relationships with other states.
    Any other option plots only migration from or to a given state. This map will be updated
    to show migration between 2019 and 2020 once new census data comes out.
    ...
    """
)

st.write(
    """
    # 🍃🌳 Green Finder 🍃🌳
    """
)
    
st.success(
    """
    マヤ車測定結果を見える化してDX、GX
    """,
    icon="🌳"
)


options = ["側方上部","側方上部(窓部)","下部","側方下部","上部"]
selection = st.pills("描画する支障位置", options, selection_mode="multi")
#, selection_mode="multi"
#st.markdown(f"Your selected options: {selection}.")

options_rank = ["A","B","C"]
selection_rank = st.pills("描画する支障ランク", options_rank, selection_mode="multi")

selection_obj = st.pills("描画する支障ランク", obj_choice, selection_mode="multi")
selection_keito = st.pills("描画する支障ランク", keito_choice, selection_mode="multi")


#st.markdown(f"Your selected options: {selection_rank}.")







tooltip = {
    "html": "通称線{通称線}<br>集計キロ程{集計キロ程}<br>支障数{judge}<br>駅名{N02_005}",
    "style": {"background": "grey", "color": "white", "font-family": '"ヒラギノ角ゴ Pro W3", "Meiryo", sans-serif', "z-index": "10000"},
}

st.pydeck_chart(
    pdk.Deck(
        map_style=None,
        tooltip=tooltip,
        initial_view_state=pdk.ViewState(
            latitude=36.63,
            longitude=140.02,
            zoom=11,
            pitch=50,
            
        ),
        layers=[
            pdk.Layer(
                "ColumnLayer",
                data=tmp2[['lon','lat','judge','通称線','集計キロ程']],
                get_position="[lon, lat]",
                get_elevation ='judge*50',
                radius=200,
                elevation_scale=10,
                elevation_range=[0, 200],
                get_fill_color=[10, 200, 50, 140],
                pickable=True,
                extruded=True,
            ),
             pdk.Layer(
                "ScatterplotLayer",
                sta,
                get_position=["lon", "lat"],  
                get_radius=500,  
                get_color=[255, 255, 255],  
                pickable=True, 
                auto_highlight=True, 
            )

        ],
    )
)


st.bar_chart(tmp2['judge'])


col_exp = st.columns(3)
with col_exp[0]:
    st.button('CSV出力')    
with col_exp[1]:
    st.button('PDF出力')    
with col_exp[2]:
    st.button('HTML出力')
