import sys
from PyQt5.QtWidgets import (QApplication, QGraphicsScene, QGraphicsView, 
                           QGraphicsItem, QGraphicsDropShadowEffect, QPushButton)
from PyQt5.QtGui import (QColor, QPen, QBrush, QPainterPath, QLinearGradient, 
                        QFont, QPainter, QIcon)
from PyQt5.QtCore import Qt, QPointF, QSize

class DiagramWindow(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setWindowTitle("Diagrama de Blocos")
        self.setGeometry(100, 100, 1200, 800)  # Modificado para 1200x800
        
        # Habilitar anti-aliasing
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Configurar fundo gradiente
        self.setBackgroundBrush(QColor(240, 240, 245))
        
        self.draw_diagram()

    def create_block(self, x, y, name, status):
        # Ajustar altura do bloco Main para acomodar os botões
        height = 100 if name == "Main" else 60
        
        # Criar caminho para bloco com cantos arredondados
        path = QPainterPath()
        path.addRoundedRect(x, y, 150, height, 15, 15)
        
        # Criar gradiente
        gradient = QLinearGradient(x, y, x, y + height)
        gradient.setColorAt(0, QColor(240, 240, 240))
        gradient.setColorAt(1, QColor(220, 220, 220))
        
        # Adicionar bloco com sombra
        block = self.scene.addPath(path, 
                                 QPen(QColor(60, 60, 60), 2), 
                                 QBrush(gradient))
        
        shadow_effect = self.create_shadow_effect()
        if shadow_effect:
            block.setGraphicsEffect(shadow_effect)
        else:
            # Criar efeito de sombra manual desenhando um retângulo escuro atrás
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(x + 3, y + 3, 150, height, 15, 15)
            shadow = self.scene.addPath(shadow_path,
                                      QPen(QColor(0, 0, 0, 0)),
                                      QBrush(QColor(0, 0, 0, 30)))
            shadow.setZValue(-1)  # Colocar sombra atrás do bloco
        
        # Adicionar texto mais acima no bloco Main
        font = QFont("Segoe UI", 10)
        text = self.scene.addText(name, font)
        text.setDefaultTextColor(QColor(40, 40, 40))
        text_y = y + 10 if name == "Main" else y + 20
        text.setPos(x + 75 - text.boundingRect().width()/2, text_y)
        
        # Adicionar indicador de status
        status_color = QColor(100, 200, 100) if status else QColor(200, 100, 100)
        status_gradient = QLinearGradient(0, 0, 0, 15)
        status_gradient.setColorAt(0, status_color.lighter(120))
        status_gradient.setColorAt(1, status_color)
        
        status_path = QPainterPath()
        status_path.addEllipse(x + 120, y + 5, 15, 15)
        status_indicator = self.scene.addPath(status_path,
                                            QPen(QColor(60, 60, 60), 1),
                                            QBrush(status_gradient))

        # Adicionar botões se for o bloco Main
        if name == "Main":
            button_style = """
                QPushButton {
                    background-color: #2E3440;
                    color: white;
                    border-radius: 8px;
                    padding: 8px 16px;
                    border: none;
                    font-family: 'Segoe UI';
                    font-weight: bold;
                    font-size: 11px;
                    width: 55px;
                    height: 32px;
                }
                QPushButton:hover {
                    background-color: #3B4252;
                    transform: translateY(-2px);
                    transition: all 0.3s ease;
                }
                QPushButton:pressed {
                    background-color: #434C5E;
                    transform: translateY(1px);
                }
                QPushButton:disabled {
                    background-color: #4C566A;
                    color: #D8DEE9;
                }
                QPushButton QIcon {
                    padding-right: 5px;
                }
            """
            
            # Botão Run com ícone e efeito de sombra
            run_button = QPushButton(" Run")  # Espaço para o ícone
            run_button.setIcon(QIcon.fromTheme('media-playback-start'))
            run_button.setIconSize(QSize(16, 16))
            run_button.setStyleSheet(button_style)
            
            run_shadow = QGraphicsDropShadowEffect()
            run_shadow.setBlurRadius(15)
            run_shadow.setOffset(0, 2)
            run_shadow.setColor(QColor(0, 0, 0, 50))
            run_button.setGraphicsEffect(run_shadow)
            
            run_proxy = self.scene.addWidget(run_button)
            run_proxy.setPos(x + 15, y + 40)

            # Botão Config com ícone
            config_button = QPushButton(" Config")  # Espaço para o ícone
            config_button.setIcon(QIcon.fromTheme('preferences-system'))
            config_button.setIconSize(QSize(16, 16))
            config_button.setStyleSheet(button_style.replace(
                "#2E3440", "#5E81AC"
            ).replace(
                "#3B4252", "#81A1C1"
            ).replace(
                "#434C5E", "#88C0D0"
            ))
            
            config_shadow = QGraphicsDropShadowEffect()
            config_shadow.setBlurRadius(15)
            config_shadow.setOffset(0, 2)
            config_shadow.setColor(QColor(0, 0, 0, 50))
            config_button.setGraphicsEffect(config_shadow)
            
            config_proxy = self.scene.addWidget(config_button)
            config_proxy.setPos(x + 80, y + 40)

            # Conectar sinais
            run_button.clicked.connect(self.run_main)
            config_button.clicked.connect(self.config_main)

        return block

    def run_main(self):
        print("Executando Main...")
        # Aqui você pode adicionar a lógica de execução do Main

    def config_main(self):
        print("Configurando Main...")
        # Aqui você pode adicionar a lógica de configuração do Main

    def create_shadow_effect(self):
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(10)
            shadow.setOffset(3, 3)
            shadow.setColor(QColor(0, 0, 0, 50))
            return shadow
        except:
            # Alternativa caso QGraphicsDropShadowEffect não esteja disponível
            return None

    def draw_curved_connection(self, start_pos, end_pos):
        path = QPainterPath()
        path.moveTo(start_pos)
        
        # Calcular pontos de controle para curva
        dx = end_pos.x() - start_pos.x()
        control_x = min(abs(dx) * 0.5, 100)
        
        path.cubicTo(
            start_pos.x() + control_x, start_pos.y(),
            end_pos.x() - control_x, end_pos.y(),
            end_pos.x(), end_pos.y()
        )
        
        # Criar conexão com gradiente
        pen = QPen(QColor(100, 100, 100), 2)
        pen.setStyle(Qt.SolidLine)
        connection = self.scene.addPath(path, pen)
        return connection

    def adjust_window_size(self):
        # Obter os limites de todos os itens na cena
        scene_rect = self.scene.itemsBoundingRect()
        
        # Adicionar margem de 50 pixels em cada lado
        margin = 50
        scene_rect.adjust(-margin, -margin, margin, margin)
        
        # Atualizar os limites da cena
        self.scene.setSceneRect(scene_rect)
        
        # Ajustar a visualização para mostrar toda a cena
        self.fitInView(scene_rect, Qt.KeepAspectRatio)
        
        # Definir tamanho mínimo da janela - convertendo para inteiros
        min_width = int(max(1200, scene_rect.width() + 2*margin))
        min_height = int(max(800, scene_rect.height() + 2*margin))
        self.setMinimumSize(min_width, min_height)
        
        # Ajustar tamanho inicial da janela
        self.resize(min_width, min_height)

    def draw_diagram(self):
        blocks = [
            {"name": "Main", "pos": (400, 350), "status": True},
            {"name": "STT", "pos": (500, 450), "status": False},
            {"name": "Skills", "pos": (700, 250), "status": True},
            {"name": "Text2Text", "pos": (700, 350), "status": True},
            {"name": "TTS", "pos": (900, 350), "status": True},
            {"name": "Short Memory", "pos": (100, 300), "status": True},
            {"name": "Long Memory", "pos": (100, 400), "status": False},
            {"name": "Character", "pos": (400, 200), "status": True},
        ]

        # Criar blocos
        block_items = []
        for block in blocks:
            block_item = self.create_block(
                block["pos"][0], block["pos"][1],
                block["name"], block["status"]
            )
            block_items.append(block_item)

        # Criar conexões
        connections = [
            (0, 1), (1, 3), (3, 4), (4, 5), (5, 0), (4, 6)
        ]

        for start_idx, end_idx in connections:
            start_block = blocks[start_idx]
            end_block = blocks[end_idx]
            
            start_pos = QPointF(
                start_block["pos"][0] + 150,
                start_block["pos"][1] + 30
            )
            end_pos = QPointF(
                end_block["pos"][0],
                end_block["pos"][1] + 30
            )
            
            self.draw_curved_connection(start_pos, end_pos)

        # Após criar todos os blocos e conexões, ajustar o tamanho da janela
        self.adjust_window_size()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reajustar a visualização quando a janela for redimensionada
        if self.scene.sceneRect():
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DiagramWindow()
    window.show()
    sys.exit(app.exec_())