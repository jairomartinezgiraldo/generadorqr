import streamlit as st
import pandas as pd
import qrcode
from reportlab.lib.pagesizes import A6
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
import base64
import os
import tempfile
from typing import List, Dict, Any, Tuple

class DataProcessor:
    """Clase para procesar y validar datos de entrada."""
    
    @staticmethod
    def validate_excel(file) -> Tuple[bool, str, pd.DataFrame]:
        """Valida el archivo Excel cargado."""
        try:
            df = pd.read_excel(file)
            
            # Verificar que el DataFrame tenga al menos una fila
            if df.empty:
                return False, "El archivo Excel no contiene datos", None
            
            # Verificar que el DataFrame tenga las columnas necesarias
            required_columns = ['id', 'nombre']  # Ajustar según necesidades
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return False, f"Faltan las siguientes columnas: {', '.join(missing_columns)}", None
            
            # Convertir todos los valores a string para evitar problemas con tipos de datos
            for col in df.columns:
                df[col] = df[col].astype(str)
            
            return True, "Archivo validado correctamente", df
        except Exception as e:
            return False, f"Error al procesar el archivo: {str(e)}", None

class QRGenerator:
    """Clase para generar códigos QR."""
    
    @staticmethod
    def generate_qr_concatenated(record: Dict[str, Any], selected_fields: List[str], separator: str = "|", box_size: int = 10) -> Tuple[Image, str]:
        """Genera un código QR a partir de varios campos concatenados y lo devuelve como una imagen de ReportLab."""
        # Concatenar los campos seleccionados con el separador
        concatenated_data = separator
        for field in selected_fields:
            value = str(record.get(field, ''))
            concatenated_data += value + separator
        
        # Generar el QR con los datos concatenados
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=4,
        )
        qr.add_data(concatenated_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Guardar la imagen en memoria
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # Crear una imagen de ReportLab directamente desde BytesIO
        return Image(img_byte_arr, width=5*cm, height=5*cm), concatenated_data

class PDFGenerator:
    """Clase para generar PDFs con etiquetas QR."""
    
    def __init__(self):
        """Inicializa el generador de PDFs con las dimensiones especificadas."""
        self.styles = getSampleStyleSheet()
        
        # Definir estilos de texto
        self.title_style = ParagraphStyle(
            'TitleStyle',
            parent=self.styles['Heading2'],
            alignment=1,  # Centrado
            spaceAfter=12,
            fontSize=12
        )
        
        self.normal_style = ParagraphStyle(
            'NormalStyle',
            parent=self.styles['Normal'],
            alignment=1,  # Centrado
            fontSize=8
        )
    
    def generate_pdf(self, records: List[Dict[str, Any]], selected_fields: List[str]) -> BytesIO:
        """Genera un PDF con todas las etiquetas en tamaño A6."""
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=A6,  # Usar tamaño A6 (10.5 x 14.8 cm)
            rightMargin=0.5*cm,
            leftMargin=0.5*cm,
            topMargin=0.5*cm,
            bottomMargin=0.5*cm
        )
        
        # Lista para almacenar todos los elementos del PDF
        elements = []
        
        # Generar una etiqueta por registro, cada una en una página separada
        for i, record in enumerate(records):
            try:
                # Título (nombre)
                if 'nombre' in record:
                    title = Paragraph(str(record['nombre']), self.title_style)
                    elements.append(title)
                
                # Añadir un espaciador
                elements.append(Spacer(1, 0.3*cm))
                
                # Generar código QR basado en los campos seleccionados concatenados
                qr_image, qr_data = QRGenerator.generate_qr_concatenated(record, selected_fields)
                
                # Añadir el QR al documento centrado
                elements.append(qr_image)
                elements.append(Spacer(1, 0.3*cm))
                
                # Crear una tabla con todos los campos del registro
                data = []
                # Primero añadir los campos seleccionados para el QR
                for field in selected_fields:
                    if field in record:
                        label = Paragraph(f"<b>{field.capitalize()}</b>:", self.normal_style)
                        value = Paragraph(str(record[field]), self.normal_style)
                        data.append([label, value])
                
                # Luego añadir los campos restantes que no están en el QR
                for key, value in record.items():
                    if key not in selected_fields and key != 'nombre':  # Excluir campos ya utilizados y nombre (ya está como título)
                        label = Paragraph(f"<b>{key.capitalize()}</b>:", self.normal_style)
                        value_text = Paragraph(str(value), self.normal_style)
                        data.append([label, value_text])
                
                # Crear la tabla
                if data:
                    table = Table(data, colWidths=[2.5*cm, 6.5*cm])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ]))
                    elements.append(table)
                
                # Añadir el contenido del QR como nota pequeña en la parte inferior
                elements.append(Spacer(1, 0.3*cm))
                qr_note = Paragraph(f"<i>QR: {qr_data}</i>", ParagraphStyle(
                    'QRNote',
                    parent=self.styles['Normal'],
                    alignment=1,
                    fontSize=6,
                    textColor=colors.gray
                ))
                elements.append(qr_note)
                
                # Añadir un salto de página después de cada etiqueta, excepto la última
                if i < len(records) - 1:
                    elements.append(PageBreak())
                
            except Exception as e:
                print(f"Error procesando registro: {record}")
                print(f"Error detallado: {str(e)}")
        
        # Construir el documento
        try:
            doc.build(elements)
        except Exception as e:
            print(f"Error construyendo el PDF: {str(e)}")
            raise
        
        pdf_buffer.seek(0)
        return pdf_buffer

class StreamlitApp:
    """Clase que maneja la interfaz gráfica en Streamlit."""
    
    def __init__(self):
        """Inicializa la aplicación con configuración básica."""
        st.set_page_config(
            page_title="Generador de Etiquetas QR",
            page_icon="🏷️",
            layout="wide"
        )
        
        # Inicializar estado de la sesión si no existe
        if 'data' not in st.session_state:
            st.session_state.data = None
            st.session_state.file_uploaded = False
            st.session_state.pdf_generated = False
            st.session_state.pdf_buffer = None
            st.session_state.selected_fields = []
    
    def run(self):
        """Ejecuta la aplicación."""
        st.title("Generador de Etiquetas QR")
        
        # Sidebar para configuración
        with st.sidebar:
            st.header("Configuración")
            
            # Subir archivo Excel
            uploaded_file = st.file_uploader("Cargar archivo Excel", type=["xlsx", "xls"])
            
            if uploaded_file is not None and not st.session_state.file_uploaded:
                # Validar el archivo
                is_valid, message, df = DataProcessor.validate_excel(uploaded_file)
                
                if is_valid:
                    st.session_state.data = df.to_dict('records')
                    st.session_state.file_uploaded = True
                    st.success(message)
                else:
                    st.error(message)
            
            if st.session_state.file_uploaded:
                # Mostrar selección de campos para el código QR
                available_fields = list(st.session_state.data[0].keys()) if st.session_state.data else []
                
                st.subheader("Campos para incluir en el QR")
                st.write("Selecciona los campos que deseas concatenar en el código QR:")
                
                # Usar checkboxes para seleccionar múltiples campos
                selected_fields = []
                for field in available_fields:
                    if st.checkbox(field, value=field in ['id', 'nombre','cantidad']):  # Por defecto seleccionar id y nombre
                        selected_fields.append(field)
                
                st.session_state.selected_fields = selected_fields
                
                # Mostrar estructura del QR resultante
                if selected_fields:
                    example_structure = "|" + "|".join(selected_fields) + "|"
                    st.write(f"Estructura resultante: `{example_structure}`")
                else:
                    st.warning("Debes seleccionar al menos un campo para el QR")
                
                # Botón para generar PDF
                if st.button("Generar PDF") and selected_fields:
                    with st.spinner("Generando etiquetas..."):
                        try:
                            # Generar PDF
                            pdf_generator = PDFGenerator()
                            pdf_buffer = pdf_generator.generate_pdf(st.session_state.data, selected_fields)
                            
                            st.session_state.pdf_buffer = pdf_buffer
                            st.session_state.pdf_generated = True
                            
                            st.success(f"PDF generado con éxito (formato A6, una etiqueta por página)")
                        except Exception as e:
                            st.error(f"Error al generar el PDF: {str(e)}")
                            st.error("Por favor, verifica que todos los campos sean válidos.")
        
        # Área principal
        if st.session_state.file_uploaded:
            st.header("Vista previa de datos")
            # Convertir la lista de diccionarios de vuelta a DataFrame para mostrarlo
            preview_df = pd.DataFrame(st.session_state.data)
            st.dataframe(preview_df, use_container_width=True)
            
            if st.session_state.pdf_generated and st.session_state.pdf_buffer:
                st.header("Descarga")
                
                # Proveer el archivo para descarga
                st.download_button(
                    label="Descargar PDF",
                    data=st.session_state.pdf_buffer,
                    file_name="etiquetas_qr_a6.pdf",
                    mime="application/pdf"
                )
        else:
            st.info("Por favor, carga un archivo Excel para comenzar.")
            
            # Mostrar ejemplo de estructura esperada
            st.header("Estructura esperada del Excel")
            example_data = {
                'id': [1001, 1002, 1003],
                'nombre': ['Producto A', 'Producto B', 'Producto C'],
                'descripcion': ['Descripción A', 'Descripción B', 'Descripción C'],
                'categoria': ['Categoría 1', 'Categoría 2', 'Categoría 1'],
                'precio': ['100', '200', '150'],
                'inventario': ['50', '30', '45']
            }
            example_df = pd.DataFrame(example_data)
            st.dataframe(example_df, use_container_width=True)
            
            st.write("El archivo debe contener al menos las columnas 'id' y 'nombre'. "
                     "Puedes añadir más columnas con información adicional que aparecerá en las etiquetas.")

# Función principal que ejecuta la aplicación
def main():
    app = StreamlitApp()
    app.run()

if __name__ == "__main__":
    main()