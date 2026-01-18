import tkinter as tk
import serial
import time
import logging
from tkinter import scrolledtext

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# 添加全局变量
is_running = False
current_serial = None
serial_connection = None  # 新增全局串口连接

# 全局日志窗口引用
log_window = None
log_text_widget = None


def get_serial_connection():
    """获取串口连接，如果未连接则新建连接"""
    global serial_connection
    if serial_connection is None or not serial_connection.is_open:
        try:
            serial_connection = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)
            time.sleep(0.5)  # 等待连接稳定
        except serial.SerialException as e:
            logging.error(f"无法连接串口: {str(e)}")
            return None
    return serial_connection


def send_command(ser, command):
    """发送命令到设备"""
    full_command = command + '\r\n'
    ser.write(full_command.encode('ascii'))
    time.sleep(0.5)  # 增加等待时间

    # 读取响应
    response = ""
    start_time = time.time()
    while time.time() - start_time < 2:  # 最多等待2秒
        if ser.in_waiting > 0:
            response += ser.read(ser.in_waiting).decode('ascii', errors='ignore')
        if response and '\n' in response:  # 如果有换行符，认为响应完整
            break
        time.sleep(0.01)

    logging.info(f"发送命令: {command}, 响应: {response}")
    return response


def execute_command(command):
    """执行指定的命令"""
    global serial_connection
    try:
        ser = get_serial_connection()
        if ser is None:
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"串口连接失败\n")
            display_text.config(state=tk.DISABLED)
            return

        result = send_command(ser, command)
        display_text.config(state=tk.NORMAL)
        display_text.insert(tk.END, f"{command}: {result}\n")
        display_text.see(tk.END)
        display_text.config(state=tk.DISABLED)
        logging.info(f"命令执行成功: {command}")
    except serial.SerialException as e:
        display_text.config(state=tk.NORMAL)
        display_text.insert(tk.END, f"串口错误: {str(e)}\n")
        display_text.config(state=tk.DISABLED)
        logging.error(f"命令执行失败: {command}, 错误: {str(e)}")
    except Exception as e:
        display_text.config(state=tk.NORMAL)
        display_text.insert(tk.END, f"执行命令 {command} 时发生错误: {str(e)}\n")
        display_text.config(state=tk.DISABLED)
        logging.error(f"命令执行失败: {command}, 错误: {str(e)}")


def run_function():
    """启动测试流程"""
    global is_running, current_serial

    if not is_running:  # 防止重复启动
        logging.info("开始执行测试流程")
        is_running = True
        run_button.config(state=tk.DISABLED)  # 禁用RUN按钮
        stop_button.config(state=tk.NORMAL)  # 启用STOP按钮

        # 记录开始时间
        start_time = time.time()

        # 更新结果显示为测试中
        result_label.config(text="Test..", bg="yellow")
        root.update_idletasks()  # 刷新界面

        try:
            logging.info("尝试连接串口 /dev/ttyUSB0")
            # 使用统一的串口连接管理
            current_serial = get_serial_connection()
            if current_serial is None:
                raise serial.SerialException("无法获取串口连接")
            logging.info("串口连接成功")

            # 发送气缸向左运动命令
            result_left = send_command(current_serial, 'CYLINDER_EXERCISE LEFT')
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"向左运动: {result_left}\n")
            display_text.see(tk.END)

            # 更新时间显示
            elapsed_time = time.time() - start_time
            time_entry.delete(0, tk.END)
            time_entry.insert(0, f"{elapsed_time:.1f}s")
            root.update_idletasks()

            time.sleep(1)  # 等待1秒

            # 发送气缸向右运动命令
            result_right = send_command(current_serial, 'CYLINDER_EXERCISE RIGHT')
            display_text.insert(tk.END, f"向右运动: {result_right}\n")
            display_text.see(tk.END)

            # 更新时间显示
            elapsed_time = time.time() - start_time
            time_entry.delete(0, tk.END)
            time_entry.insert(0, f"{elapsed_time:.1f}s")
            root.update_idletasks()

            display_text.config(state=tk.DISABLED)

            # 测试完成，显示总时间
            total_time = time.time() - start_time
            time_entry.delete(0, tk.END)
            time_entry.insert(0, f"{total_time:.1f}s")

            # 假设测试成功，更新结果为Pass
            result_label.config(text="Pass", bg="lightgreen")
            logging.info("测试完成，结果: Pass")

            is_running = False

            # 重置按钮状态
            run_button.config(state=tk.NORMAL)
            stop_button.config(state=tk.DISABLED)

        except serial.SerialException as e:
            logging.error(f"串口错误: {str(e)}")
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"串口错误: {str(e)}\n")
            display_text.config(state=tk.DISABLED)
            # 测试失败，更新结果为Fail
            result_label.config(text="Fail", bg="red")
            is_running = False

            # 重置按钮状态
            run_button.config(state=tk.NORMAL)
            stop_button.config(state=tk.DISABLED)



def stop_function():
    """停止当前测试"""
    global is_running, current_serial

    logging.info("执行停止操作")
    is_running = False
    run_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)

    # 关闭当前串口连接（如果存在）
    if current_serial and current_serial.is_open:
        current_serial.close()
        current_serial = None
        logging.info("串口连接已关闭")

    # 更新结果显示为停止
    result_label.config(text="Stopped", bg="orange")

    # 清空时间显示
    time_entry.delete(0, tk.END)
    time_entry.insert(0, "0.0s")


def show_command_window():
    """显示控制指令窗口"""
    command_window = tk.Toplevel(root)
    command_window.title("H60机台指令")
    command_window.geometry("300x400")
    command_window.configure(bg="lightgray")

    # H60机台指令按钮
    tk.Button(command_window, text="Help", command=lambda: execute_command('help'), bg="lightblue").pack(pady=2,
                                                                                                         fill=tk.X)
    tk.Button(command_window, text="Start_test", command=lambda: execute_command('Start_test'), bg="lightgreen").pack(
        pady=2, fill=tk.X)
    tk.Button(command_window, text="End_test Pass", command=lambda: execute_command('End_test pass'),
              bg="lightyellow").pack(pady=2, fill=tk.X)
    tk.Button(command_window, text="End_test Fail", command=lambda: execute_command('End_test fail'),
              bg="lightyellow").pack(pady=2, fill=tk.X)
    tk.Button(command_window, text="Reset", command=lambda: execute_command('Reset'), bg="lightcoral").pack(pady=2,
                                                                                                            fill=tk.X)
    tk.Button(command_window, text="Is_Button_Pressed", command=lambda: execute_command('Is_Button_Pressed'),
              bg="lightblue").pack(pady=2, fill=tk.X)
    tk.Button(command_window, text="CYLINDER_RESET", command=lambda: execute_command('CYLINDER_RESET'),
              bg="lightgreen").pack(pady=2, fill=tk.X)
    tk.Button(command_window, text="CYLINDER_EXERCISE RIGHT",
              command=lambda: execute_command('CYLINDER_EXERCISE RIGHT'), bg="lightyellow").pack(pady=2, fill=tk.X)
    tk.Button(command_window, text="CYLINDER_EXERCISE LEFT", command=lambda: execute_command('CYLINDER_EXERCISE LEFT'),
              bg="lightyellow").pack(pady=2, fill=tk.X)
    tk.Button(command_window, text="FixtureSN", command=lambda: execute_command('FixtureSN'), bg="lightcoral").pack(
        pady=2, fill=tk.X)
    tk.Button(command_window, text="Version", command=lambda: execute_command('Version'), bg="lightblue").pack(pady=2,
                                                                                                               fill=tk.X)


def show_log_window():
    """在主文本框显示日志内容"""
    try:
        with open('app.log', 'r', encoding='utf-8') as f:
            log_content = f.read()
            display_text.config(state=tk.NORMAL)
            display_text.delete(1.0, tk.END)  # 清空当前内容
            display_text.insert(tk.END, "=== 日志内容 ===\n")
            display_text.insert(tk.END, log_content)
            display_text.see(tk.END)
            display_text.config(state=tk.DISABLED)
    except FileNotFoundError:
        display_text.config(state=tk.NORMAL)
        display_text.delete(1.0, tk.END)  # 清空当前内容
        display_text.insert(tk.END, "日志文件不存在，将从现在开始记录日志...\n")
        display_text.see(tk.END)
        display_text.config(state=tk.DISABLED)


def cleanup_serial():
    """清理串口连接"""
    global serial_connection
    if serial_connection and serial_connection.is_open:
        serial_connection.close()
        serial_connection = None


# 创建主窗口
root = tk.Tk()
root.title("Simple RUN Result GUI")
root.geometry("850x550")

# 设置主窗口背景色
root.configure(bg="green")
# 禁止窗口调整大小
root.resizable(False, False)

# 左侧按钮列框架
left_frame = tk.Frame(root, bg="white")
left_frame.grid(row=0, column=0, padx=(20, 5), pady=20, sticky=tk.N)

# RUN结果标签（移到最上方）
result_frame = tk.Frame(left_frame, bg="white")
result_frame.pack(pady=5)
tk.Label(result_frame, text="Result:", bg="white").pack(side=tk.LEFT)
result_label = tk.Label(result_frame, text="Ready", bg="lightgray", width=8, relief="sunken")
result_label.pack(side=tk.LEFT, padx=(5, 0))

# 左侧按钮列中的RUN和STOP按钮
run_button = tk.Button(left_frame, text="RUN", command=run_function, bg="red", fg="black", width=10)
run_button.pack(pady=5)

stop_button = tk.Button(left_frame, text="STOP", command=stop_function, bg="orange", fg="black", width=10)
stop_button.pack(pady=5)
# 初始时禁用STOP按钮
stop_button.config(state=tk.DISABLED)

# SN标签和输入框
sn_frame = tk.Frame(left_frame, bg="white")
sn_frame.pack(pady=5)
tk.Label(sn_frame, text="SN:", bg="white").pack(side=tk.LEFT)
sn_entry = tk.Entry(sn_frame, width=10)
sn_entry.pack(side=tk.LEFT, padx=(5, 0))

# Time标签和输入框
time_frame = tk.Frame(left_frame, bg="white")
time_frame.pack(pady=5)
tk.Label(time_frame, text="Time:", bg="white").pack(side=tk.LEFT)
time_entry = tk.Entry(time_frame, width=8)
time_entry.pack(side=tk.LEFT, padx=(5, 0))

# 在显示框顶部添加按钮（不含RUN和SN按钮）
display_frame = tk.Frame(root, bg="white")
display_frame.grid(row=0, column=1, padx=(5, 20), pady=20, sticky=tk.NW)

button_frame = tk.Frame(display_frame, bg="white")
button_frame.pack(fill=tk.X, pady=(0, 10))

# 顶部按钮（Test Result, Test Process, Test Command）
tk.Button(button_frame, text="Test Result", command=lambda: None, bg="lightblue").pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Test Process", command=show_log_window, bg="lightgreen").pack(side=tk.LEFT, padx=5)
tk.Button(button_frame, text="Test Command", command=show_command_window, bg="lightyellow").pack(side=tk.LEFT, padx=5)

# 显示框（在按钮下方）
display_text = tk.Text(
    display_frame,
    width=85,
    height=42.5,
    font=("Arial", 10)
)
display_text.pack()

display_text.config(state=tk.DISABLED)

# 设置窗口关闭事件
root.protocol("WM_DELETE_WINDOW", lambda: [cleanup_serial(), root.destroy()])

# 启动主循环
root.mainloop()
