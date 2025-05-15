import pandas as pd
import streamlit as st
import pydeck as pdk
import plotly.express as px
import geopandas as gpd
from shapely import wkt
import time
from functools import wraps
from typing import Callable, Any

# 環境設定
### Streamlitの初期設定
st.set_page_config(page_title="Green Finder", 
                   layout="wide", page_icon="🌳",
                   initial_sidebar_state="expanded")

### 起点となるパス設定
# ローカルの場合: ""　コンテナの場合: "src/"
path = 'src/'
path = ''

# デバッグモード設定（本番環境ではFalseに設定）
DEBUG_MODE = False
# DEBUG_MODE = st.sidebar.toggle("デバッグモード")    # UIで切り替えたいとき

# パフォーマンス計測デコレータ
def measure_time(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        if not DEBUG_MODE:
            return func(*args, **kwargs)
        
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        st.sidebar.info(f"⏱️ {func.__name__} 実行時間: {end_time - start_time:.4f}秒")
        return result
    return wrapper


@st.cache_data
def rail_load():
    ### CSV読込み
    ## 座標データ
    kilo = pd.read_csv(path + "kirotei_lonlat.csv", encoding="shift_jis")
    ## 駅データ
    sta = pd.read_csv(path + "station_lonlat_jre.csv", encoding="shift_jis")
    ## 路線データ
    line = pd.read_csv(path + "tsushosen_line.csv", encoding="shift_jis")    # uploaded_file がある場合、2回読み込まれてしまうため変更

    
    ### データ下処理
    ## 駅データ
    sta['label'] = sta['N02_003'].astype(str) + str(" ") + sta['N02_005'].astype(str)
    
    ## 路線データ
    line['label'] = line['通称線']
    line['geometry'] = line['WKT'].apply(wkt.loads)
    line_gdf = gpd.GeoDataFrame(line, geometry='geometry')
    
    return kilo, sta, line_gdf


@measure_time
def main():
    # 線路条件をCSVから読み込む
    kilo, sta, line_gdf = rail_load()
    
    # タイトル表示
    top_view = st.container()
    top_view.write("""# 🍃🌳 Green Finder - Beta""")   
    
    ### サイドバーの設定
    with st.sidebar:
        st.write("""## データ読込""")  
        uploaded_file = st.file_uploader('マヤ車測定結果Excelをアップロード', type=['xlsx'])
        if uploaded_file is not None:
            st.write('アップロードされたファイル:', uploaded_file.name)
            # content = uploaded_file.read()    # 使用していなかったためコメントアウト
            # data_raw = uploaded_file
            #data_raw = pd.read_csv(uploaded_file, encoding="shift_jis")
            data_raw = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            ## サンプルデータ
            data_raw = pd.read_csv(path + "sample_empty.csv", encoding="shift_jis")    # uploaded_file がある場合、2回読み込まれてしまうため変更
            top_view.info('👈サイドバーからデータをアップロードしてください。')
            #return
            
        # st.dataframe(data_raw[['測定日']])
        data_raw['date'] = pd.to_datetime(data_raw['測定日']).dt.date
        
        tsusho_choice = data_raw['通称線'].unique() 
        junk = data_raw[["通称線","走行方向"]].drop_duplicates()
        junk['表示'] = False
        junkbox = st.data_editor(junk)
        
        selected_pairs = junkbox[junkbox['表示'] == True][['通称線', '走行方向']]

        st.write(selected_pairs)
      
        selectbox_senku = st.selectbox("線名", tsusho_choice)
    
        if selectbox_senku not in kilo['線名'].unique():
            st.warning('選択した線名に該当する座標データがありません。「使用手順と注意」を参照してください。',icon="🔥")
        
        dir_choice = data_raw[(data_raw['通称線']==selectbox_senku)]['走行方向'].unique()
        selectbox_direction = st.selectbox("走行方向", dir_choice)
        # pressed = st.form_submit_button("マップ更新")
    

        interval = st.number_input("集計間隔[m]", value=200, min_value=10, max_value=2000, step=10, format="%i")

        if interval % 200 == 100:
            kilo['キロ程'] = kilo['キロ程'] + 50
        data_raw['集計キロ程'] = data_raw['キロ程']//interval*interval+int(interval/2)
        
        data_raw2 = data_raw.merge(kilo[['線名','キロ程','経度','緯度','箇所名']].drop_duplicates(subset=['線名','キロ程']),left_on=['集計キロ程','通称線'],right_on=['キロ程','線名'])
        
        st.write('保技セエリア')
        options_kasho = data_raw2[(data_raw2['通称線']==selectbox_senku)&(data_raw2['走行方向']==selectbox_direction)]['箇所名'].unique()
        selectbox_kasho = [option for option in options_kasho if st.checkbox(option, value=True)]
    
        # st.info('現在テスト中のため、烏山線、山手貨物線のデータをデフォルトで読み込んでいますが、新たにデータをアップすると、新しいデータに上書きされます。',icon="💡")

    ### 測定データの処理２
    data = data_raw2[(data_raw2['通称線']==selectbox_senku)&(data_raw2['走行方向']==selectbox_direction)&(data_raw2['箇所名'].isin(selectbox_kasho))&(data_raw2['ビデオ確認による対象物'].isin(['草木']))]


    filtered_data = data_raw2.merge(selected_pairs, on=['通称線', '走行方向'])
    data = filtered_data[(filtered_data['箇所名'].isin(selectbox_kasho)) &(filtered_data['ビデオ確認による対象物'] == '草木')]

  
    # obj_choice =data['ビデオ確認による対象物'].unique()
    # keito_choice =data['支障物確認を行う担当分野'].unique()
    # LR_choice = data['位置'].unique()
    
    ### 閾値による支障判定
    ## 建築限界判定（すべてカウント）
    data['建築限界判定'] = 1
    
    ## 車両限界判定閾値（部位別閾値）
    limit_s_dict = { "側方上部": 400,"側方上部(窓部)": 200,"下部": 50, "側方下部": 50,"上部": 200}
    data['lim_s'] = data['支障位置'].map(limit_s_dict)
    data['車両限界判定'] =0
    data['車両限界判定'] = (data['支障量'] >= data['lim_s']).astype(int)

    for position in limit_s_dict.keys():
        data[f'建築限界判定_{position}'] = ((data['建築限界判定'] == 1) & (data['支障位置'] == position)).astype(int)
        data[f'車両限界判定_{position}'] = ((data['車両限界判定'] == 1) & (data['支障位置'] == position)).astype(int)

    ### メインページ
    st.write('## 表示設定')
    
    ### 表示項目設定
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
        st.write('左右')
        selection_LR = [option for option in ["左","右"] if st.checkbox(option, value=True)]
        
    with col0[3]:
        radius = st.slider("駅サイズ", min_value=100, max_value=1000, value=500, step=100)
        wid = st.slider("路線太さ", min_value=50, max_value=500, value=300, step=50)
    with col0[4]:
        elevation_scale = st.slider("棒グラフ長さ", min_value=1, max_value=20, value=10, step=1)
        elevation_radius = st.slider("棒グラフ太さ", min_value=100, max_value=500, value=200, step=50)
    
    ### 測定データの処理３
    
    # data['集計キロ程'] = data['キロ程']//interval*interval+int(interval/2)
    # data_filter = data[(data['支障位置'].isin(selection))&(data['暫定ランク'].isin(selection_rank))&(data['ビデオ確認による対象物'].isin(selection_obj))&(data['支障物確認を行う担当分野'].isin(selection_keito))]
    data_filter = data[(data['支障位置'].isin(selection))&(data['暫定ランク'].isin(selection_rank))&(data['位置'].isin(selection_LR))]
    
    tmp = data_filter.groupby(['通称線','集計キロ程'])[['建築限界判定','建築限界判定_側方上部','建築限界判定_側方上部(窓部)','建築限界判定_下部','建築限界判定_側方下部','建築限界判定_上部','車両限界判定','車両限界判定_側方上部','車両限界判定_側方上部(窓部)','車両限界判定_下部','車両限界判定_側方下部','車両限界判定_上部']].sum().reset_index()
    tmp2 = tmp.merge(kilo[['線名','キロ程','経度','緯度','箇所名']].drop_duplicates(subset=['線名','キロ程']),left_on=['集計キロ程','通称線'],right_on=['キロ程','線名'])
    tmp2 = tmp2.rename(columns={'経度': 'lon', '緯度': 'lat'})
    tmp2['label'] = str('線名：　')+tmp2['通称線'].astype(str) + str('<br>キロ程範囲：')+(tmp2['集計キロ程']-interval/2).astype(int).astype(str)+ "-" + (tmp2['集計キロ程']+interval/2).astype(int).astype(str) + str('<br>建築限界支障数：　')+tmp2['建築限界判定'].astype(str) + str('<br>車両限界支障数：　')+tmp2['車両限界判定'].astype(str)
    tmp3 = tmp2[tmp2['箇所名'].isin(selectbox_kasho)]
    
    summary = {
    '建築限界支障': [data['建築限界判定'].sum(), data_filter['建築限界判定'].sum()],
    '車両限界支障': [data['車両限界判定'].sum() , data_filter['車両限界判定'].sum()]
    }
    df_summary = pd.DataFrame(summary)
    df_summary.index = ['全数', '表示中']
    # st.dataframe(df_summary.T)
        
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
                    use_container_width=False,
                    width="100%", 
                    height=1200
                ),
                layers=[
                    pdk.Layer(
                        "ColumnLayer",
                        data=tmp3[['lon','lat','建築限界判定','通称線','集計キロ程','label']],
                        get_position="[lon, lat]",
                        get_elevation ='建築限界判定*50',
                        radius=elevation_radius,
                        elevation_scale=elevation_scale,
                        elevation_range=[0, 200],
                        get_fill_color=[152, 251, 152, 140],
                        pickable=True,
                        extruded=True,
                        auto_highlight=True
                    ),
                    pdk.Layer(
                    "ColumnLayer",
                    data=tmp3[['lon','lat','建築限界判定','車両限界判定','通称線','集計キロ程','label']],
                    get_position="[lon, lat]",
                    get_elevation ='車両限界判定*50',
                    radius=elevation_radius,
                    elevation_scale=elevation_scale,
                    elevation_range=[0, 200],
                    get_fill_color=[0, 100, 0, 140],
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
                        pickable=True,
                    )
                    ],
            )
        )
    with tab2:  
        fig = px.bar(tmp3, x='集計キロ程', y=['建築限界判定','車両限界判定'], 
                 title=selectbox_senku,
                 labels={'集計キロ程': '集計キロ程', '支障数': '建築限界判定'},
                    color_discrete_map={'建築限界判定': 'palegreen', '車両限界判定': 'darkgreen'})
        fig.update_xaxes(tickvals=tmp3['集計キロ程'],  # 既存の値を使用
            ticktext=[f"{val // 1000}k{val % 1000:03}m" for val in tmp3['集計キロ程']] )
        st.plotly_chart(fig)
    with tab3:
        st.dataframe(tmp3[['通称線','集計キロ程','建築限界判定','建築限界判定_側方上部','建築限界判定_側方上部(窓部)','建築限界判定_下部','建築限界判定_側方下部','建築限界判定_上部','車両限界判定','車両限界判定_側方上部','車両限界判定_側方上部(窓部)','車両限界判定_下部','車両限界判定_側方下部','車両限界判定_上部']])
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
            -入力するcsvデータは加工（セル結合、列追加削除等）していないものを用いてください。\n
            -入力データの「キロ程」に数値以外が混ざっていないことを確認してください。（カンマ、ピリオド、英字等があれば削除）\
            -地図に表示できる（緯度経度と紐づけできる）線名は以下です。入力データとの整合を確認してください。一致する線名が無い場合はエラーとなります。\n
        ''')
        # st.table(pd.DataFrame(kilo['線名'].unique(), columns=['読込可能な線名']))
        st.markdown(kilo[['線名コード','線名']].drop_duplicates(subset='線名コード').style.hide(axis="index").to_html(), unsafe_allow_html=True)


if __name__ == "__main__":
    start_time = time.time()
    main()
    if DEBUG_MODE:
        end_time = time.time()
        st.sidebar.info(f"⏱️ 全体実行時間: {end_time - start_time:.4f}秒")
