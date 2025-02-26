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
import plotly.express as px
import geopandas as gpd
from shapely import wkt

try:
    print('doing')
    path = os.path.dirname(os.path.abspath(__file__))+"\\"
except:
    print("skip")
    path = os.getcwd()+"\\"

###関数
def color_green(val):
    color = 'green' if val == '建築限界' else ''
    return f'background-color: {color}'
    
###ファイルパス設定（直下またはgithubのURLを参照する）
#path = 'C:/Users/yone/Documents/PythonScripts/g_finder/'
#path = 'https://github.com/yoneshin357/g_finder/blob/main/'
#path = 'https://github.com/yoneshin357/g_finder/raw/refs/heads/main/'
path= ''

###CSVを読み込む
kilo = pd.read_csv(path+"tizukiro.csv", encoding="shift_jis")
sta = pd.read_csv(path+"station_jre.csv", encoding="shift_jis")
data = pd.read_csv(path+"karasuyama.csv", encoding="shift_jis")
line = pd.read_csv(path+"tsusho.csv", encoding="shift_jis")

###sta駅の下処理
#sta['通称線'] = np.nan
#sta['集計キロ程'] = np.nan
#sta['支障数'] = np.nan
sta['label'] = sta['N02_003'].astype(str) +str(" ")+ sta['N02_005'].astype(str)

###line路線の下処理
line['label'] = line['通称線']
line['geometry'] = line['WKT'].apply(wkt.loads)
line_gdf = gpd.GeoDataFrame(line, geometry='geometry')

###data測定データの下処理（１）
data['date'] = pd.to_datetime(data['測定日']).dt.date
tsusho_choice = data['通称線'].unique()
dir_choice = data['走行方向'].unique()
date_choice = data['date'].unique()

### Streamlitアプリの設定
st.set_page_config(page_title="Green Finder", 
                   layout="wide", page_icon="🌳",
                   initial_sidebar_state="expanded")
#st.write("path="+str(path))

### CSS設定
st.markdown(
    """
    <style>
    div[role="listbox"] ul {
        background-color: #f0f0f0; /* 背景色を変更 */
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.markdown(
    """
    <style>
    .fixed-title {
        position: fixed;
        top: 0;
        width: 100%;
        z-index: 1000;
        border-bottom: 1px solid #e6e6e6;
        padding: 10px 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)


###サイドバーの設定
with st.sidebar.form(key="my_form"):
    st.write("""## データ読込""")  
    uploaded_file = st.file_uploader('マヤ車測定結果csvをアップロード', type=['csv'])
    if uploaded_file is not None:
        st.write('アップロードされたファイル:', uploaded_file.name)
        content = uploaded_file.read()
        data = uploaded_file
    selectbox_senku = st.selectbox("線名", tsusho_choice)
    selectbox_direction = st.selectbox("走行方向", dir_choice)
    number_threshold = st.number_input("集計間隔[m]", value=200, min_value=100, max_value=2000, step=100, format="%i")
    #st.write('支障カウント閾値')
    #edited_limit = st.data_editor(limit_dmy)
    #option_mode = st.radio(
    #"支障判定モードを選択してください:",
    #('建築限界モード', '車両限界モード')    )
    pressed = st.form_submit_button("マップ更新")
    #st.success(    """    マヤ車測定結果を見える化してDX、GX    """,    icon="🌳")
    st.info('現在テスト中のため、烏山線、山手貨物線のデータをデフォルトで読み込んでいますが、新たにデータをアップすると、新しいデータに上書きされます。',icon="💡")


###data下処理（２）（線名、走行方向、草木）
#data = data[data['通称線']==selectbox_senku]
data = data[(data['通称線']==selectbox_senku)&(data['走行方向']==selectbox_direction)&(data['ビデオ確認による対象物'].isin(['草木']))]
obj_choice =data['ビデオ確認による対象物'].unique()
keito_choice =data['支障物確認を行う担当分野'].unique()
LR_choice = data['位置'].unique()

#expander = st.sidebar.expander("連絡先")
#expander.write(    """    設備部門土木ユニット　xxx-xxxx    ...    """)


#建築限界
limit_k =  pd.DataFrame({"閾値": pd.Series([0, 0, 0, 0, 0])})
limit_k.index=["側方上部","側方上部(窓部)","下部","側方下部","上部"]
limit_k_dict = limit_k.to_dict(orient='dict')['閾値']

#車両限界
limit_s =  pd.DataFrame({"閾値": pd.Series([400, 200, 50, 50, 200])})
limit_s.index=["側方上部","側方上部(窓部)","下部","側方下部","上部"]
limit_s_dict = limit_s.to_dict(orient='dict')['閾値']


#if option_mode == '建築限界モード':
#    print(1)
#else:
#    print(1)


data['lim_k'] = data['支障位置'].map(limit_k_dict)
data['lim_s'] = data['支障位置'].map(limit_s_dict)

data['建築限界判定']=0
data['車両限界判定']=0

data['建築限界判定'] = (data['支障量'] >= data['lim_k']).astype(int)
data['車両限界判定'] = (data['支障量'] >= data['lim_s']).astype(int)

for position in limit_k_dict.keys():
    data[f'建築限界判定_{position}'] = ((data['建築限界判定'] == 1) & (data['支障位置'] == position)).astype(int)
    data[f'車両限界判定_{position}'] = ((data['車両限界判定'] == 1) & (data['支障位置'] == position)).astype(int)

st.write("""# 🍃🌳 Green Finder""")    
st.write('### 表示項目設定')

col0 = st.columns(5)
with col0[0]:
    st.write('支障位置')
    options = ["側方上部","側方上部(窓部)","下部","側方下部","上部"]
    selection = [option for option in options if st.checkbox(option, value=True)]

with col0[1]:
    st.write('暫定ランク')
    options_rank = ["A(即日)","A","B","C"]
    selection_rank = [option for option in options_rank if st.checkbox(option, value=True)]
with col0[2]:
    #st.write('対象物')
    #selection_obj = [option for option in obj_choice if st.checkbox(option, value=(option == "草木"))]
    st.write('左右')
    selection_LR = [option for option in LR_choice if st.checkbox(option, value=True)]
    
with col0[3]:
    #st.write('空きスペース')
    #selection_keito = [option for option in keito_choice if st.checkbox(option, value=True)]
    radius = st.slider("駅サイズ", min_value=100, max_value=1000, value=500, step=100)
    wid = st.slider("路線太さ", min_value=50, max_value=500, value=300, step=50)


#項目によるデータの絞り込み
intvl = number_threshold
data['集計キロ程'] = data['キロ程']//intvl*intvl+int(intvl/2)
#data_filter = data[(data['支障位置'].isin(selection))&(data['暫定ランク'].isin(selection_rank))&(data['ビデオ確認による対象物'].isin(selection_obj))&(data['支障物確認を行う担当分野'].isin(selection_keito))]
data_filter = data[(data['支障位置'].isin(selection))&(data['暫定ランク'].isin(selection_rank))&(data['位置'].isin(selection_LR))]


tmp = data_filter.groupby(['通称線','走行方向','date','集計キロ程'])[['建築限界判定','建築限界判定_側方上部','建築限界判定_側方上部(窓部)','建築限界判定_下部','建築限界判定_側方下部','建築限界判定_上部','車両限界判定','車両限界判定_側方上部','車両限界判定_側方上部(窓部)','車両限界判定_下部','車両限界判定_側方下部','車両限界判定_上部']].sum().reset_index()
tmp2 = tmp.merge(kilo[['線名','キロ程','経度','緯度']].drop_duplicates(subset=['線名','キロ程']),left_on=['集計キロ程','通称線'],right_on=['キロ程','線名'])
tmp2 = tmp2.rename(columns={'経度': 'lon', '緯度': 'lat'})
tmp2['label'] = str('線名：　')+tmp2['通称線'].astype(str) + str('<br>キロ程範囲：')+(tmp2['集計キロ程']-intvl/2).astype(int).astype(str)+ "-" + (tmp2['集計キロ程']+intvl/2).astype(int).astype(str) + str('<br>建築限界支障数：　')+tmp2['建築限界判定'].astype(str) + str('<br>車両限界支障数：　')+tmp2['車両限界判定'].astype(str)

with col0[4]:

    elevation_scale = st.slider("棒スケール", min_value=1, max_value=20, value=10, step=1)

    #st.download_button(
    #label="集計表CSV出力",
    #data=tmp2.to_csv(index=False).encode('cp932'),
    #file_name='test.csv',
    #mime='text/csv')



summary = {

'建築限界支障': [data['建築限界判定'].sum(), data_filter['建築限界判定'].sum()],
'車両限界支障': [data['車両限界判定'].sum() , data_filter['車両限界判定'].sum()]
}

df_summary = pd.DataFrame(summary)
df_summary.index = ['全数', '表示中']

st.dataframe(df_summary.T)

tttt = pd.crosstab(data['支障位置'], [data['建築限界判定'],data['車両限界判定']], dropna=False)
tttt2 =  = pd.crosstab(data['支障位置'], data['車両限界判定'], dropna=False)
tttt = tttt.reindex(options,fill_value=0)
tttt2 =  = tttt2.reindex(options,fill_value=0)
st.dataframe(tttt)

    
tab1, tab2, tab3, tab4 = st.tabs(["３次元地図", "グラフ","集計表","使用手順と注意"])
with tab1:






    
    tooltip = {
        "html": "{label}",
        "style": {"background": "grey", "color": "white", "font-family": '"ヒラギノ角ゴ Pro W3", "Meiryo", sans-serif', "z-index": "10000"},
    }
    #"通称線{通称線}<br>集計キロ程中心{集計キロ程}<br>支障数{judge}<br>駅名{N02_005}"
    st.pydeck_chart(
        pdk.Deck(
            map_style=None,
            tooltip=tooltip,
            initial_view_state=pdk.ViewState(
                latitude=36.63,
                longitude=140.02,
                zoom=7,
                pitch=50,
                idth="100%",  # 幅を800ピクセルに設定
                height=800  # 高さを600ピクセルに設定
            ),
            layers=[

                pdk.Layer(
                    "ColumnLayer",
                    data=tmp2[['lon','lat','建築限界判定','通称線','集計キロ程','label']],
                    get_position="[lon, lat]",
                    get_elevation ='建築限界判定*50',
                    radius=200,
                    elevation_scale=elevation_scale,
                    elevation_range=[0, 200],
                    get_fill_color=[10, 200, 50, 140],
                    pickable=True,
                    extruded=True,
                ),
                pdk.Layer(
                "ColumnLayer",
                data=tmp2[['lon','lat','建築限界判定','車両限界判定','通称線','集計キロ程','label']],
                get_position="[lon, lat]",
                get_elevation ='車両限界判定*50',
                radius=200,
                elevation_scale=elevation_scale,
                elevation_range=[0, 200],
                get_fill_color=[10, 50, 200, 140],
                pickable=True,
                extruded=True,
                ),
                 pdk.Layer(
                    "ScatterplotLayer",
                    sta,
                    get_position=["lon", "lat"],  
                    get_radius=radius,  
                    get_color=[255, 244, 79],  
                    pickable=True, 
                    auto_highlight=True, 
                ),
                 pdk.Layer(
                    "GeoJsonLayer",
                    data=line_gdf,
                    get_line_width=wid,  # ラインの太さを設定
                    get_line_color=[255, 244, 79],  # ラインの色を設定（赤色）
                )
    
            ],
        )
    )

# タブ2の内容
with tab2:
    
    fig = px.bar(tmp2, x='集計キロ程', y=['建築限界判定','車両限界判定'], 
             title=selectbox_senku,
             labels={'集計キロ程': '集計キロ程', '支障数': '建築限界判定'})
    fig.update_xaxes(
        tickvals=tmp2['集計キロ程'],  # 既存の値を使用
        ticktext=[f"{val // 1000}k{val % 1000:03}m" for val in tmp2['集計キロ程']]  # フォーマット
    )
    # Streamlitでグラフを表示
    st.plotly_chart(fig)


with tab3:
    st.dataframe(tmp2[['通称線','走行方向','date','集計キロ程','建築限界判定','建築限界判定_側方上部','建築限界判定_側方上部(窓部)','建築限界判定_下部','建築限界判定_側方下部','建築限界判定_上部','車両限界判定','車両限界判定_側方上部','車両限界判定_側方上部(窓部)','車両限界判定_下部','車両限界判定_側方下部','車両限界判定_上部']])




with tab4:
    st.write("""## 🌳 使用手順""")
    st.markdown('''
        1.マヤ車測定結果の生データをアップロードする。\n
    2.表示する線名を設定する。\n
    3.支障判定モードを設定する。\n
    4.マップ更新ボタンを押下。\n
    5.マップ表示設定を適宜切り替える。
    ''')
    st.write("""## 🌳 注意点""")
    st.markdown('''
        -入力するcsvデータは一切加工していないものを用いてください。\n
    -地図に表示できる（緯度経度と紐づけできる）線名は以下です。入力データとの整合を確認してください。一致する線名が無い場合はエラーとなります。\n
    ''')
    st.table(pd.DataFrame(kilo['線名'].unique(), columns=['読込可能な線名']))



#st.markdown(f"Your selected options: {selection_rank}.")










