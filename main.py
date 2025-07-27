from ._anvil_designer import HomeTemplate
from anvil import *
import anvil.js
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables
import plotly.graph_objects as go
import time
#from ..DemoTrend import DataProvider

class Home(HomeTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    # khởi tạo data để dùng cho plot
    self.data_points = []
    self.annotations = []
    #khai báo các nút sự kiện rang
    self.annotation_buttons = [
      self.btn_Charge, self.btn_Dry_End,
      self.btn_Fc_Start, self.btn_Fc_End,
      self.btn_Sc_Start, self.btn_Sc_End,
      self.btn_Drop, self.btn_Cool_End
    ]
    self.current_phase = 0   # chọn pha để hiển thị LCD bên javascript
    # 🔧 Biến theo dõi turning point
    self.prev_bt_buffer = []            # dùng để lưu 6 giá trị BT gần nhất để tìm turning point
    self.monitor_turning_point = False  # Có đang theo dõi turning point không?
    self.turning_point_found = False    # Đã tìm thấy chưa?
    self.prev_temp = None               # Nhiệt độ trước đó


  """----init-page ----------------------------------------------------------------------------------------------
  * @author: ChungNguyen
  * @nav: + các nút chuyển đổi page được customer bằng các css và gán (inactive/active)
          + các icon được biến đổi màu từ code nội
  * @plot: + được khởi tạo sau khi page đã hoàn thành tránh quá nhiều tác vụ chồng chéo gây lag
  * @event: gán hàm update cho timer xử lý
  """
  def form_show(self, **event_args):
    self.layout.reset_links()
    self.layout.button_home.role = "custom-icon-button-active"
    self.layout.button_home.foreground = "white"
    self.plot_old_append_point()
    self.timer_1.add_event_handler('tick', self.home_update)

    self.label_valET.text = 0.0
    self.label_valBT.text = 0.0
    self.label_valDeltaET.text = 0.0
    self.label_valDeltaBT.text = 0.0

    self.label_valChamber.text = 0
    self.label_valPercentGas.text = 0
    self.label_valPercentAir.text = 0
    self.label_valPercentDrum.text = 0
    
  """----cập nhật các giá trị trên home-------------------------------------------------------------------------
  * @author: ChungNguyen
  * @binding: lấy các giá trị ở cột cuối cùng gán cho self.item để các text binding dữ liệu đến.
  * @plot:  + th1: nếu trên biểu đồ không có bất kì trace nào được vễ tiến hành đọc dữ liệu cũ để tải điểm đầu
            + th2: nếu trên biễu đồ đã có trace tiến hành vẽ các điểm kéo dài từ point cũ để tối ưu tốc đô 
  """
  def home_update(self, **event_args):
    with anvil.server.no_loading_indicator: # không hiện vòng xoay
      #1. binding monitor giá trị hàng cuối cùng 
      rows = list(tables.app_tables.datatab.search())
      if rows:
        self.item = rows[-1]

      #2. nếu chưa có trace nào được tạo -> lấy dữ liệu từ data để tạo ra trace
      if len(self.fig.data) == 0: 
        self.plot_old_append_point()
        self.update_phase_js()
      #3. nếu đã có trace -> vẽ nối trace để tới ưu
      else:
        #3.1 đọc bảng data
        rows = list(tables.app_tables.datatab.search(tables.order_by("time", ascending=True))) 
        if not rows:
          return
        latest = rows[-1]
        #3.2 kiểm tra nếu có điểm mới thì add vào data_points
        if not self.data_points or self.data_points[-1]['time'] != latest['time']:
          self.data_points.append({
            "time": latest['time'],
            "BT": latest['BT'],
            "ET": latest['ET'],
            "drum": latest['drum'],
            "air": latest['air'],
            "burner": latest['burner'],
            "ΔBT": latest['delta_bt'],
            "ΔET": latest['delta_et']
          })
          self.plot_new_latest_point()

  
  """----vẽ lại các giá trị cũ từ table data-------------------------------------------------------------------------
  * @modify: ChungNguyen
  * @def: plot_old_append_point(self) ~ hàm chức năng vẽ lại data cũ từ data
  * @ax: _plot_old_load_data(self) ~ hàm phụ trợ lấy dữ liệu từ data table
  * @ax: _plot_old_show(self) ~ hàm phụ trợ khởi tạo plot
  * @ax: _plot_old_set_layout(self) ~ hàm phụ trợ setlayout
  * @ax: _plot_old_update_plot(self) ~ hàm phụ trợ vẽ trace
  """
  def plot_old_append_point(self):
    self.data_points = [] # clear data
    self.annotations = [] # clear data
    self._plot_old_load_data() # lấy dữ liệu cũ
    self._plot_old_show() # vẽ lại đường từ dữ liệu đã có từ data table

  def _plot_old_load_data(self):
    rows = app_tables.datatab.search(tables.order_by("time", ascending=True)) # lấy dữ liệu ra từ table
    for row in rows: # đưa dữ liệu vào data_points để xử lý
      self.data_points.append({
        "time": row['time'],
        "BT": row['BT'],
        "ET": row['ET'],
        "drum": row['drum'],
        "air": row['air'],
        "burner": row['burner'],
        "ΔBT": row['delta_bt'],
        "ΔET": row['delta_et']
      })

  def _plot_old_show(self):
    current_time = self.data_points[-1]['time'] if self.data_points else 0
  
    # Tạo trace ảo để ép hiển thị yaxis2 khi chưa có dữ liệu Delta BT, ET
    dummy_trace = go.Scatter(
      x=[0, 1],
      y=[0, 1],
      yaxis='y',
      mode='lines',
      name='dummy_y2',
      line=dict(color='rgba(0,0,0,0)'),
      showlegend=False
    )
    dummy_trace1 = go.Scatter(
      x=[0, 1],
      y=[0, 1],
      yaxis='y2',
      mode='lines',
      name='dummy_y2',
      line=dict(color='rgba(0,0,0,0)'),
      showlegend=False
    )
  
    # Gắn luôn vào data khi tạo figure
    self.fig = go.Figure(
      data=[dummy_trace,dummy_trace1],
      layout=self._plot_old_set_layout(current_time)
    )
    
    # Lấy tất cả các label đã lưu từ bảng annotationtab để gắn vào trend
    rows = app_tables.annotationtab.search()
    for row in rows:
      self.annotations.append(dict(
        x=row['time'],
        y=row['bt'],
        text=row['label'],
        showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1,
        arrowcolor="red", font=dict(color="red", size=10),
        bgcolor="rgba(0,0,0,0)", ax=row['ax'], ay=row['ay']
      ))
    # Nếu label đó là annotation từ nút và bị disabled thì tắt lại nút tương ứng
      if row.get('disabled'):
        label_lower = row['label'].lower()
        for btn in self.annotation_buttons:
          if label_lower.startswith(btn.text.lower()):
            btn.enabled = False
      self.current_phase = row.get('phase')
    self.plot_1.figure = self.fig
    self._plot_old_update_plot()


  def _plot_old_set_layout(self, current_time):
    return go.Layout(
      title=dict(text="Realtime Roasting"),
      xaxis=dict(
        title=dict(text="Time (min)"),
        range=[0, max(20, current_time + 1)],
        tick0=0,
        dtick=2,
        rangeslider=dict(visible=False),
        type="linear"
      ),
      yaxis=dict(
        title=dict(text="Temperature (°C)"),
        side="left",
        range=[1, 400],
        showgrid=True,
        rangemode='tozero',
        showticklabels = True,
      ),
      yaxis2=dict(
        title=dict(text="ΔTemperature (°C/min)"),
        overlaying="y",
        side="right",
        range=[0, 50],
        autorange=False,
        showgrid=False,
        showline=True,
        linewidth=1,
      ),
      annotations=self.annotations,
      shapes=[
        dict(
          type="line",
          xref="x", yref="paper",
          x0=current_time, x1=current_time,
          y0=0, y1=1,
          line=dict(color="red", width=2, dash="solid")
        )
      ],
      height=500,
      margin=dict(l=40, r=50, t=40, b=40),
      showlegend=True,
      dragmode='pan'
    )

  #----------------------Chuyển định dạng time sec sang 00:00-----------------------------
  def format_time(self, seconds):
    total_seconds = int(seconds * 60)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes}:{secs:02d}"
    
  def _plot_old_update_plot(self):
    if not self.data_points:
      return
    #--Chuyển data thành dic
    x = [d['time']/60.0 for d in self.data_points]
    bt = [d['BT'] for d in self.data_points]
    et = [d['ET'] for d in self.data_points]
    drum = [d['drum'] for d in self.data_points]
    air = [d['air'] for d in self.data_points]
    burner = [d['burner'] for d in self.data_points]
    delta_bt = [d['ΔBT'] for d in self.data_points]
    delta_et = [d['ΔET'] for d in self.data_points]

    current_time = x[-1]
    data = [
      go.Scatter(x=x, y=bt, name='BT', yaxis='y1', mode='lines', line=dict(width=2),
                 customdata=[self.format_time(t) for t in x],
                 hovertemplate='BT: %{y}<br>Time: %{customdata}<extra></extra>'),
      go.Scatter(x=x, y=et, name='ET', yaxis='y1', mode='lines', line=dict(width=2),
                 hovertemplate='ET: %{y}<br>Time: %{customdata}<extra></extra>',
                 customdata=[self.format_time(t) for t in x]),
      go.Scatter(x=x, y=drum, name='%Drum', yaxis='y1', mode='lines', line=dict(width=2),
                 hovertemplate='%Drum: %{y}<br>Time: %{customdata}<extra></extra>',
                 customdata=[self.format_time(t) for t in x]),
      go.Scatter(x=x, y=air, name='%Air', yaxis='y1', mode='lines', line=dict(width=2),
                 hovertemplate='%Air: %{y}<br>Time: %{customdata}<extra></extra>',
                 customdata=[self.format_time(t) for t in x]),
      go.Scatter(x=x, y=burner, name='%Burner', yaxis='y1', mode='lines', line=dict(width=2),
                 hovertemplate='%Burner: %{y}<br>Time: %{customdata}<extra></extra>',
                 customdata=[self.format_time(t) for t in x]),
      go.Scatter(x=x, y=delta_bt, name='ΔBT', yaxis='y2', mode='lines', line=dict(color='red', dash='dash', width=2),
                 hovertemplate='ΔBT: %{y}<br>Time: %{customdata}<extra></extra>',
                 customdata=[self.format_time(t) for t in x]),
      go.Scatter(x=x, y=delta_et, name='ΔET', yaxis='y2', mode='lines', line=dict(color='orange', dash='dot', width=2),
                 hovertemplate='ΔT: %{y}<br>Time: %{customdata}<extra></extra>',
                 customdata=[self.format_time(t) for t in x])
    ]
    # Dự đoán BT, ET
    if len(x) >= 10:
      recent_x = x[-10:]
      recent_bt = bt[-10:]
      slope_bt = (recent_bt[-1] - recent_bt[0]) / (recent_x[-1] - recent_x[0] + 1e-6)
      y_bt_start = bt[-1]
      forecast_bt_y = [y_bt_start, y_bt_start + slope_bt * (60 - x[-1])]

      data.append(go.Scatter(
        x=[x[-1], current_time + 5],
        y=forecast_bt_y,
        mode='lines',
        name='BT forecast',
        line=dict(color='red', dash='dashdot', width=7),
        opacity=0.2,
        showlegend=False,
        hoverinfo='skip'
      ))

      recent_et = et[-10:]
      slope_et = (recent_et[-1] - recent_et[0]) / (recent_x[-1] - recent_x[0] + 1e-6)
      y_et_start = et[-1]
      forecast_et_y = [y_et_start, y_et_start + slope_et * (current_time + 5 - x[-1])]

      data.append(go.Scatter(
        x=[x[-1], current_time + 5],
        y=forecast_et_y,
        mode='lines',
        name='ET forecast',
        line=dict(color='blue', dash='dashdot', width=7),
        opacity=0.2,
        showlegend=False,
        hoverinfo='skip'
      ))

    self.fig = go.Figure(data=data, layout=self._plot_old_set_layout(current_time))
    self.fig.update_layout(uirevision='static')
    self.plot_1.figure = self.fig
    
  """----vẽ các điểm mới---------------------------------------------------------------------------------------------------
  * @author: ChungNguyen
  * @extend_trace: chức năng vẽ các điểm mới từ điểm cũ cuối cùng đã vẽ
  """
  def plot_new_latest_point(self):
    if len(self.data_points) == 0:  #chưa có dữ liệu
      return
    if not hasattr(self, 'fig'): #self fig chưa được tạo
      return
    if len(self.fig.data) == 0: #chưa có trace nào được tạo
      return
  
    d = self.data_points[-1]
    new_x = d['time'] / 60.0  # đổi đơn vị giây → phút
    formatted_time = self.format_time(new_x)
  
    # Append vào từng trace
    self.fig.data[0].x += (new_x,)
    self.fig.data[0].y += (d['BT'],)
    self.fig.data[0].customdata += ((formatted_time,),)

    self.fig.data[1].x += (new_x,)
    self.fig.data[1].y += (d['ET'],)
    self.fig.data[1].customdata += ((formatted_time,),)

    self.fig.data[2].x += (new_x,)
    self.fig.data[2].y += (d['drum'],)
    self.fig.data[2].customdata += ((formatted_time,),)

    self.fig.data[3].x += (new_x,)
    self.fig.data[3].y += (d['air'],)
    self.fig.data[3].customdata += ((formatted_time,),)

    self.fig.data[4].x += (new_x,)
    self.fig.data[4].y += (d['burner'],)
    self.fig.data[4].customdata += ((formatted_time,),)

    self.fig.data[5].x += (new_x,)
    self.fig.data[5].y += (d['ΔBT'],)
    self.fig.data[5].customdata += ((formatted_time,),)

    self.fig.data[6].x += (new_x,)
    self.fig.data[6].y += (d['ΔET'],)
    self.fig.data[6].customdata += ((formatted_time,),)

    #-----DỰ ĐOÁN BT & ET--------------------------------------
    if len(self.data_points) >= 10:
      # Dữ liệu X và Y
      x_vals = [dp['time'] / 60.0 for dp in self.data_points]
      bt_vals = [dp['BT'] for dp in self.data_points]
      et_vals = [dp['ET'] for dp in self.data_points]
    
      recent_x = x_vals[-10:]
      recent_bt = bt_vals[-10:]
      recent_et = et_vals[-10:]
    
      current_time = new_x
      forecast_time = current_time + 5
    
      # BT forecast
      slope_bt = (recent_bt[-1] - recent_bt[0]) / (recent_x[-1] - recent_x[0] + 1e-6)
      y_bt_start = bt_vals[-1]
      forecast_bt_y = [y_bt_start, y_bt_start + slope_bt * (forecast_time - current_time)]
    
      # ET forecast
      slope_et = (recent_et[-1] - recent_et[0]) / (recent_x[-1] - recent_x[0] + 1e-6)
      y_et_start = et_vals[-1]
      forecast_et_y = [y_et_start, y_et_start + slope_et * (forecast_time - current_time)]
    
      # Giữ lại 7 trace đầu tiên (xóa forecast cũ nếu có)
      base_traces = list(self.fig.data[:7])
    
      # Thêm forecast trace mới
      forecast_traces = [
        go.Scatter(
          x=[current_time, forecast_time],
          y=forecast_bt_y,
          mode='lines',
          name='BT forecast',
          line=dict(color='red', dash='dashdot', width=7),
          opacity=0.2,
          showlegend=False
        ),
        go.Scatter(
          x=[current_time, forecast_time],
          y=forecast_et_y,
          mode='lines',
          name='ET forecast',
          line=dict(color='blue', dash='dashdot', width=7),
          opacity=0.2,
          showlegend=False
        )
      ]
    
      # Gán lại data cho fig
      self.fig.data = base_traces + forecast_traces

      
    #-----Cập nhật đường thời gian dọc--------------------------------------
    self.fig.update_layout(shapes=[
        dict(
          type="line",
          xref="x", yref="paper",
          x0=new_x, x1=new_x,
          y0=0, y1=1,
          line=dict(color="red", width=2, dash="solid")
        )
      ])
    self.check_turning_point()
    self.plot_1.figure = self.fig  # Gán lại để hiển thị cập nhật

  #----button even 2---------------------------------------------------
  def button_reset_click(self, **event_args):
    self.label_status.text = anvil.server.call("write_holding_registers", 1, 1)
    self.label_status.text = anvil.server.call("write_holding_registers", 0, 0)
    #xóa hết các label trên biểu đồ
    app_tables.annotationtab.delete_all_rows()
    self.annotations = []
    app_tables.datatab.delete_all_rows()
    #  Bật lại tất cả các nút annotation
    if hasattr(self, "annotation_buttons"):
      for btn in self.annotation_buttons:
        btn.enabled = True
    self._plot_old_update_plot()
    

  def button_on_click(self, **event_args):
    self.label_status.text = anvil.server.call("write_holding_registers", 0, 1)
    pass

  def slider_Air_change(self, level, **event_args):
    self.label_slider_air.text = self.slider_Air.level
    pass

  def slider_burner_change(self, level, **event_args):
    self.label_slider_buner.text = self.slider_burner.level
    pass

  def slider_Drum_change(self, level, **event_args):
    self.label_slider_drum.text = self.slider_Drum.level
    pass

  #-------------------Thêm label mỗi khi có sự kiện rang ---------------------------

  def add_bt_annotation(self, label_text, source_btn):
    # Nếu chưa có biểu đồ hoặc chưa có trace nào thì thoát
    if not hasattr(self, 'fig') or len(self.fig.data) == 0:
      return
  
    # Lấy thời gian x và nhiệt độ y cuối cùng từ trace BT
    trace = self.fig.data[0]  # trace BT
    x_time = trace.x[-1]      # thời gian theo phút
    y_bt = trace.y[-1]        # nhiệt độ hiện tại
  
    # Format nhãn thời gian dạng CHARGE 0:23
    minutes = int(x_time)
    seconds = int((x_time - minutes) * 60)
    time_label = f"{label_text} {minutes}:{seconds:02d}"
    temp_label = f"{y_bt:.1f}°C"
  
    # ---- Vẽ lên biểu đồ 2 annotation: thời gian và nhiệt độ ----
    self.annotations.append(dict(
      x=x_time, y=y_bt, text=time_label,
      showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1,
      arrowcolor="red", font=dict(color="red", size=10),
      bgcolor="rgba(0,0,0,0)", ax=20, ay=40
    ))
  
    self.annotations.append(dict(
      x=x_time, y=y_bt, text=temp_label,
      showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1,
      arrowcolor="red", font=dict(color="red", size=10),
      bgcolor="rgba(0,0,0,0)", ax=20, ay=-40
    ))
  
    # ----  Lưu 2 annotation vào bảng `annotationtab` ----
    app_tables.annotationtab.add_row(time=x_time, bt=y_bt, label=time_label, ax=20, ay=40, disabled=True, phase=self.current_phase)
    app_tables.annotationtab.add_row(time=x_time, bt=y_bt, label=temp_label, ax=20, ay=-40, disabled=False, phase=self.current_phase)
    
    # Cập nhật lại biểu đồ để vẽ annotation
    self._plot_old_update_plot()
  
    # Disable các nút trước đó
    if hasattr(self, "annotation_buttons"):
      index = self.annotation_buttons.index(source_btn)
      for i in range(index + 1):
        self.annotation_buttons[i].enabled = False


  #----------------------Check turning point-----------------------------
  def check_turning_point(self):
    if not self.monitor_turning_point or self.turning_point_found:
      return

    if len(self.data_points) < 2:
      return

    temp = self.data_points[-1]["BT"]

    # Lần đầu gọi thì khởi tạo prev_temp
    if self.prev_temp is None:
      self.prev_temp = temp
      return

    # Nếu đang giảm thì cập nhật prev_temp
    if temp < self.prev_temp:
      self.prev_temp = temp

    # Nếu vừa tăng lần đầu sau chuỗi giảm, đánh dấu TURNING
    elif temp > self.prev_temp:
      self.add_bt_annotation("TP", self.btn_Charge)
      self.turning_point_found = True
      self.monitor_turning_point = False
      self.prev_temp = None  # reset để nếu CHARGE lại thì có thể theo dõi tiếp




  def btn_Charge_click(self, **event_args):
    self.add_bt_annotation("CHARGE", self.btn_Charge)
    self.monitor_turning_point = True
    self.turning_point_found = False
    self.prev_temp = None
    self.current_phase = 1
    self.update_phase_js()


  def btn_Dry_End_click(self, **event_args): 
    self.add_bt_annotation("DRY END", self.btn_Dry_End)
    self.current_phase = 2
    self.update_phase_js()
    
  def btn_Fc_Start_click(self, **event_args): 
    self.add_bt_annotation("FC START", self.btn_Fc_Start)
    self.current_phase = 3
    self.update_phase_js()
    
  def btn_Fc_End_click(self, **event_args): 
    self.add_bt_annotation("FC END", self.btn_Fc_End)
    self.current_phase = 3
    self.update_phase_js()
    
  def btn_Sc_Start_click(self, **event_args): 
    self.add_bt_annotation("SC START", self.btn_Sc_Start)
    self.current_phase = 3
    self.update_phase_js()
    
  def btn_Sc_End_click(self, **event_args): 
    self.add_bt_annotation("SC END", self.btn_Sc_End)
    self.current_phase = 3
    self.update_phase_js()
    
  def btn_Drop_click(self, **event_args): 
    self.add_bt_annotation("DROP", self.btn_Drop)
    self.current_phase = 3
    self.update_phase_js()
    
  def btn_Cool_End_click(self, **event_args): 
    self.add_bt_annotation("COOL END", self.btn_Cool_End)
    self.current_phase = 3
    self.update_phase_js()
    
  def update_phase_js(self):
    """Gửi phase hiện tại qua JavaScript"""
    anvil.js.call_js("setPhase", self.current_phase)



