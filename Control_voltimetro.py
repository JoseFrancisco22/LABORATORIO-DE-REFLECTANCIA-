import tkinter as tk
from tkinter import ttk, messagebox
import pyvisa
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import numpy as np

class VoltajeDCApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Medición Continua de Voltaje DC")
        self.geometry("800x600")
        
        # Variables de estado
        self.rm = None
        self.multimetro = None
        self.connected = False
        self.measuring = False
        
        # Datos para la gráfica
        self.tiempos = []
        self.voltajes = []
        self.max_puntos = 1000  # Máximo de puntos en la gráfica
        
        self.create_widgets()
        
        # Intentar inicializar pyvisa
        try:
            self.rm = pyvisa.ResourceManager()
            self.actualizar_dispositivos()
        except Exception as e:
            print(f"Error al inicializar PyVISA: {e}")

    def create_widgets(self):
        # Frame de controles
        control_frame = ttk.Frame(self, padding="10")
        control_frame.pack(fill="x")
        
        # Selección de dispositivo
        ttk.Label(control_frame, text="Dispositivo:").grid(row=0, column=0, padx=5, pady=5)
        self.dispositivo_var = tk.StringVar()
        self.dispositivo_combo = ttk.Combobox(control_frame, textvariable=self.dispositivo_var, width=30)
        self.dispositivo_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Actualizar", command=self.actualizar_dispositivos).grid(row=0, column=2, padx=5, pady=5)
        
        # Botones de control
        self.conectar_btn = ttk.Button(control_frame, text="Conectar", command=self.toggle_conexion)
        self.conectar_btn.grid(row=0, column=3, padx=5, pady=5)
        
        self.medir_btn = ttk.Button(control_frame, text="Iniciar Medición", command=self.toggle_medicion, state="disabled")
        self.medir_btn.grid(row=0, column=4, padx=5, pady=5)
        
        # Display del voltaje actual
        ttk.Label(control_frame, text="Voltaje Actual:", font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=10)
        self.voltaje_var = tk.StringVar(value="0.000 V")
        voltaje_label = ttk.Label(control_frame, textvariable=self.voltaje_var, font=("Arial", 16, "bold"), foreground="blue")
        voltaje_label.grid(row=1, column=1, columnspan=2, padx=5, pady=10)
        
        # Frame de la gráfica
        graph_frame = ttk.Frame(self)
        graph_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Configurar la gráfica
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.ax.set_xlabel('Tiempo (s)')
        self.ax.set_ylabel('Voltaje (V)')
        self.ax.set_title('Medición Continua de Voltaje DC')
        self.ax.grid(True, alpha=0.3)
        
        # Línea inicial de la gráfica
        self.line, = self.ax.plot([], [], 'b-', linewidth=1)
        
        self.canvas = FigureCanvasTkAgg(self.fig, graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Barra de estado
        self.status_var = tk.StringVar(value="Listo")
        status_label = ttk.Label(self, textvariable=self.status_var, relief="sunken")
        status_label.pack(fill="x", padx=10, pady=5)

    def actualizar_dispositivos(self):
        try:
            dispositivos = self.rm.list_resources()
            self.dispositivo_combo['values'] = dispositivos
            if dispositivos:
                self.dispositivo_combo.set(dispositivos[0])
            self.status_var.set(f"Dispositivos encontrados: {len(dispositivos)}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    def toggle_conexion(self):
        if self.connected:
            self.desconectar()
        else:
            self.conectar()

    def conectar(self):
        try:
            dispositivo = self.dispositivo_var.get()
            if not dispositivo:
                messagebox.showerror("Error", "Selecciona un dispositivo")
                return
            
            self.multimetro = self.rm.open_resource(dispositivo)
            self.multimetro.timeout = 5000  # 5 segundos
            
            # Configurar para medición de voltaje DC
            self.multimetro.write("CONF:VOLT:DC")
            
            self.connected = True
            self.conectar_btn.config(text="Desconectar")
            self.medir_btn.config(state="normal")
            self.status_var.set(f"Conectado a {dispositivo}")
            
        except Exception as e:
            messagebox.showerror("Error de conexión", f"No se pudo conectar: {e}")

    def desconectar(self):
        if self.measuring:
            self.measuring = False
            time.sleep(0.5)
        
        if self.multimetro:
            self.multimetro.close()
        
        self.connected = False
        self.conectar_btn.config(text="Conectar")
        self.medir_btn.config(state="disabled")
        self.medir_btn.config(text="Iniciar Medición")
        self.status_var.set("Desconectado")

    def toggle_medicion(self):
        if self.measuring:
            self.measuring = False
            self.medir_btn.config(text="Iniciar Medición")
            self.status_var.set("Medición detenida")
        else:
            self.measuring = True
            self.medir_btn.config(text="Detener Medición")
            self.status_var.set("Medición en curso...")
            
            # Limpiar datos anteriores
            self.tiempos.clear()
            self.voltajes.clear()
            self.line.set_data([], [])
            
            # Iniciar medición continua en hilo separado
            threading.Thread(target=self.medicion_continua, daemon=True).start()
            
            # Iniciar animación de la gráfica
            self.anim = FuncAnimation(self.fig, self.actualizar_grafica, interval=100, cache_frame_data=False)

    def medicion_continua(self):
        tiempo_inicio = time.time()
        
        while self.measuring and self.connected:
            try:
                # Leer voltaje DC
                self.multimetro.write("MEAS:VOLT:DC?")
                respuesta = self.multimetro.read().strip()
                
                # Convertir a número
                voltaje = float(respuesta)
                tiempo_actual = time.time() - tiempo_inicio
                
                # Actualizar en el hilo principal
                self.after(0, self.actualizar_datos, tiempo_actual, voltaje)
                
                # Pequeña pausa entre mediciones
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error en medición: {e}")
                time.sleep(0.5)

    def actualizar_datos(self, tiempo, voltaje):
        # Agregar nuevos datos
        self.tiempos.append(tiempo)
        self.voltajes.append(voltaje)
        
        # Mantener solo los últimos max_puntos puntos
        if len(self.tiempos) > self.max_puntos:
            self.tiempos.pop(0)
            self.voltajes.pop(0)
        
        # Actualizar display
        self.voltaje_var.set(f"{voltaje:.6f} V")

    def actualizar_grafica(self, frame):
        if self.tiempos and self.voltajes:
            self.line.set_data(self.tiempos, self.voltajes)
            
            # Ajustar límites de la gráfica
            if len(self.tiempos) > 1:
                self.ax.set_xlim(min(self.tiempos), max(self.tiempos))
                
                voltaje_min = min(self.voltajes)
                voltaje_max = max(self.voltajes)
                margen = (voltaje_max - voltaje_min) * 0.1
                self.ax.set_ylim(voltaje_min - margen, voltaje_max + margen)
            
            self.canvas.draw_idle()
        
        return self.line,

    def __del__(self):
        if self.multimetro:
            self.multimetro.close()

if __name__ == "__main__":
    app = VoltajeDCApp()
    app.mainloop()
