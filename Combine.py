import tkinter as tk
import serial
import time
import logging
import csv
import socket  # 添加socket导入
from tkinter import filedialog, scrolledtext
import pexpect
import subprocess
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
test_results_data = []  # 存储测试结果数据
test_start_time = None
test_end_time = None

# 第二个串口连接相关变量
second_serial_connection = None
second_serial_port = '/dev/cu.usbserial-112201'  # 第二个串口端口
second_serial_baudrate = 115200  # 波特率

# TCP/IP连接相关变量
tcp_socket = None
tcp_connected = False
tcp_ip_address = "127.0.0.1"  # 默认IP地址
tcp_port = 8080  # 默认端口

# 全局日志窗口引用
log_window = None
log_text_widget = None


def get_serial_connection():
    """获取串口连接，如果未连接则新建连接"""
    global serial_connection
    if serial_connection is None or not serial_connection.is_open:
        try:
            serial_connection = serial.Serial('/dev/cu.usbserial-Control', 115200, timeout=2)
            time.sleep(0.5)  # 等待连接稳定
        except serial.SerialException as e:
            logging.error(f"无法连接串口: {str(e)}")
            return None
    return serial_connection


def get_second_serial_connection():
    """获取第二个串口连接，如果未连接则新建连接"""
    global second_serial_connection
    if second_serial_connection is None or not second_serial_connection.is_open:
        try:
            second_serial_connection = serial.Serial(second_serial_port, second_serial_baudrate, timeout=2)
            time.sleep(0.5)  # 等待连接稳定
        except serial.SerialException as e:
            logging.error(f"无法连接第二个串口: {str(e)}")
            return None
    return second_serial_connection


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


def connect_tcp(ip_address="127.0.0.1", port=8080):
    """连接TCP/IP服务器"""
    global tcp_socket, tcp_connected, tcp_ip_address, tcp_port
    tcp_ip_address = ip_address
    tcp_port = port

    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(5)  # 设置5秒超时
        tcp_socket.connect((tcp_ip_address, tcp_port))
        tcp_connected = True
        logging.info(f"TCP/IP连接成功: {tcp_ip_address}:{tcp_port}")
        return True
    except Exception as e:
        logging.error(f"TCP/IP连接失败: {str(e)}")
        tcp_connected = False
        return False


def send_tcp_data(data):
    """通过TCP/IP发送数据"""
    global tcp_socket, tcp_connected
    if tcp_connected and tcp_socket:
        try:
            tcp_socket.sendall(data.encode('utf-8'))
            logging.info(f"TCP/IP发送数据: {data}")
            return True
        except Exception as e:
            logging.error(f"TCP/IP发送数据失败: {str(e)}")
            tcp_connected = False
            return False
    else:
        logging.warning("TCP/IP未连接，无法发送数据")
        return False


def disconnect_tcp():
    """断开TCP/IP连接"""
    global tcp_socket, tcp_connected
    if tcp_socket:
        try:
            tcp_socket.close()
            logging.info("TCP/IP连接已断开")
        except:
            pass
    tcp_socket = None
    tcp_connected = False


def get_unit_sn():
    """获取Unit_SN值，通过adb命令获取"""
    try:
        # 执行 adb root
        subprocess.run(['adb', 'root'], check=True, timeout=10)

        # 执行 adb shell oai-sn get 并获取输出
        result = subprocess.run(['adb', 'shell', 'oai-sn', 'get'],
                                capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            unit_sn = result.stdout.strip()
            logging.info(f"获取到Unit_SN: {unit_sn}")
            return unit_sn
        else:
            logging.error(f"adb shell oai-sn get 执行失败: {result.stderr}")
            return "unknown_unit_sn"

    except subprocess.TimeoutExpired:
        logging.error("adb命令执行超时")
        return "timeout_unit_sn"
    except subprocess.CalledProcessError as e:
        logging.error(f"adb命令执行失败: {e}")
        return "error_unit_sn"
    except Exception as e:
        logging.error(f"获取Unit_SN失败: {str(e)}")
        return "unknown_unit_sn"


def read_mmwave_device_info():
    """读取mmwave设备信息，直接在终端执行nanokdp命令"""
    try:
        # 启动 nanokdp 命令
        child = pexpect.spawn('nanokdp -c 1000000,n,8,1')
        # 等待设备选择提示
        child.expect('Select a device by its number')
        # 选择设备编号 4
        child.sendline('3')
        child.sendline('')  # 空字符串相当于按回车键
        # 等待命令执行完成，出现命令提示符
        # 这里需要根据实际的提示符进行调整
        child.expect(['>', '#', r'\$', 'nanokdp>', pexpect.TIMEOUT], timeout=10)
        # 发送回车键确认选择（如果需要）
        child.sendline('')  # 空字符串相当于按回车键
        # 执行 mmwave status 命令
        child.sendline('mmwave status')
        # 等待命令输出完成
        child.expect(['>', '#', r'\$', 'nanokdp>', pexpect.EOF], timeout=15)
        # 获取命令输出结果
        output = child.before.decode('utf-8', errors='ignore')
        # 解析输出，查找Device信息
        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('Device:'):
                device_part = line[7:].strip()  # 去掉 "Device:" 前缀
                child.close()
                return device_part
        child.close()
        return None
    except pexpect.exceptions.TIMEOUT:
        logging.error("pexpect命令执行超时")
        return None
    except Exception as e:
        logging.error(f"执行pexpect命令失败: {str(e)}")
        return None




def periodically_read_and_upload():
    """定期读取mmwave设备信息并上传到TCP服务器"""
    info = read_mmwave_device_info()  # 替换为新函数
    if info:
        # 准备上传数据
        upload_data = {
            'device_type': 'mmwave_device',
            'timestamp': time.time(),
            'info': info
        }
        # 发送数据到TCP服务器
        send_tcp_data(str(upload_data))

        # 同时更新SN文本框
        root.after(0, lambda: update_sn_display(info))

    # 5秒后再次执行
    root.after(5000, periodically_read_and_upload)


def update_sn_display(device_info):
    """更新SN显示框"""
    if device_info:
        sn_entry.delete(0, tk.END)
        sn_entry.insert(0, device_info)


def run_function():
    """启动测试流程"""
    global is_running, current_serial, test_results_data, test_start_time, test_end_time

    if not is_running:  # 防止重复启动
        logging.info("开始执行测试流程")
        # 清空之前的测试结果
        test_results_data = []
        # 记录测试开始时间
        test_start_time = time.strftime('%Y-%m-%d %H:%M:%S')

        is_running = True
        run_button.config(state=tk.DISABLED)  # 禁用RUN按钮
        stop_button.config(state=tk.NORMAL)  # 启用STOP按钮

        # 记录开始时间
        start_time = time.time()

        # 更新结果显示为测试中
        result_label.config(text="Test..", bg="yellow")
        root.update_idletasks()  # 刷新界面

        try:
            logging.info("尝试连接串口 /dev/cu.usbserial-Control")
            # 使用统一的串口连接管理
            current_serial = get_serial_connection()
            if current_serial is None:
                raise serial.SerialException("无法获取串口连接")
            logging.info("串口连接成功")

            # 先获取设备序列号并填充到SN输入框
            fixture_sn_response = send_command(current_serial, 'FixtureSN')
            # 提取序列号（通常响应格式为 "FixtureSN: ABC123" 或类似格式）
            extracted_sn = fixture_sn_response.strip()
            if ':' in extracted_sn:
                extracted_sn = extracted_sn.split(':', 1)[1].strip()
            elif extracted_sn.startswith('FixtureSN'):
                extracted_sn = extracted_sn[10:].strip()  # 移除'FixtureSN'前缀

            # 更新SN输入框
            sn_entry.delete(0, tk.END)
            sn_entry.insert(0, extracted_sn)

            # 发送气缸向左运动命令
            result_left = send_command(current_serial, 'CYLINDER_EXERCISE LEFT')
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"向左运动: {result_left}\n")
            display_text.see(tk.END)

            # 记录测试结果
            test_results_data.append({
                'command': 'CYLINDER_EXERCISE LEFT',
                'result': result_left,
                'timestamp': time.time() - start_time
            })

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

            # 记录测试结果
            test_results_data.append({
                'command': 'CYLINDER_EXERCISE RIGHT',
                'result': result_right,
                'timestamp': time.time() - start_time
            })

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

            # 记录测试结束时间
            test_end_time = time.strftime('%Y-%m-%d %H:%M:%S')


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
            # 记录测试结束时间
            test_end_time = time.strftime('%Y-%m-%d %H:%M:%S')
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


def export_to_csv():
    """导出测试结果到CSV文件"""
    global test_results_data, test_start_time, test_end_time

    # 获取mmwave设备信息
    device_part = read_mmwave_device_info()  # 调用函数获取设备信息
    print(f"获取到的设备信息: {device_part}")  # 添加调试输出

    # 获取Unit_SN
    unit_sn = get_unit_sn()  # 添加这一行

    # 初始化失败列表
    fail_list = []
    # 检查测试数据中的错误
    for data in test_results_data:
        if 'fail' in data['result'].lower() or 'error' in data['result'].lower():
            fail_list.append(data['command'])
    # 如果有具体的错误条件，可以添加判断
    if result_label.cget('text') == 'Fail':
        fail_list.append('Overall_Test_Failed')

    # 获取保存文件路径
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        title="保存测试结果"
    )

    if file_path:
        try:
            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Unit_SN', 'Start_Time',
                              'End_Time', 'Station_ID','Fixture_SN', 'mmWAVE_Model_Name', 'Test_Result','Fail_list','Timestamp', 'Total_Time' ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                # 写入测试数据
                sn_value = sn_entry.get()  # 获取SN输入框的值
                total_time = time_entry.get()  # 获取总时间
                test_status = result_label.cget('text')  # 获取测试结果状态
                start_time_str = test_start_time if test_start_time else 'N/A'
                end_time_str = test_end_time if test_end_time else 'N/A'
                for data in test_results_data:
                    writer.writerow({
                        'Unit_SN':unit_sn,
                        'Start_Time':start_time_str,
                        'End_Time': end_time_str,
                        'Station_ID': 'N/A',
                        'Fixture_SN': sn_value,
                        'mmWAVE_Model_Name': device_part,
                        'Test_Result': data['result'],
                        'Fail_list':';'.join(fail_list) if fail_list else 'N/A',
                        'Timestamp': f"{data['timestamp']:.2f}s",
                        'Total_Time': total_time,
                    })

                # 如果没有测试数据，至少输出一行基本信息
                if not test_results_data:
                    writer.writerow({
                        'Unit_SN': unit_sn,
                        'Start_Time': start_time_str,
                        'End_Time': end_time_str,
                        'Station_ID': 'N/A',
                        'Fixture_SN': sn_value,
                        'mmWAVE_Model_Name': device_part if device_part else 'N/A',
                        'Test_Result': 'N/A',
                        'Fail_list':';'.join(fail_list) if fail_list else 'N/A',
                        'Timestamp': '0.00s',
                        'Total_Time': total_time,
                    })

            # 在界面上显示导出成功信息
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"\n测试结果已导出到: {file_path}\n")
            display_text.see(tk.END)
            display_text.config(state=tk.DISABLED)

        except Exception as e:
            display_text.config(state=tk.NORMAL)
            display_text.insert(tk.END, f"导出CSV失败: {str(e)}\n")
            display_text.see(tk.END)
            display_text.config(state=tk.DISABLED)


def cleanup_serial():
    """清理串口和TCP连接"""
    global serial_connection, second_serial_connection
    if serial_connection and serial_connection.is_open:
        serial_connection.close()
        serial_connection = None

    if second_serial_connection and second_serial_connection.is_open:
        second_serial_connection.close()
        second_serial_connection = None

    # 断开TCP连接
    if tcp_socket:
        try:
            tcp_socket.close()
        except:
            pass
        tcp_socket = None


# 创建主窗口
root = tk.Tk()
root.title("H60_mmwave GUI")
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
tk.Button(button_frame, text="Test Result", command=export_to_csv, bg="lightblue").pack(side=tk.LEFT, padx=5)
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

# 在程序启动时连接TCP并启动定期读取
connect_tcp()
root.after(1000, periodically_read_and_upload)  # 1秒后开始

# 启动主循环
root.mainloop()
