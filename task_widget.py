import json
from PyQt5 import QtWidgets, QtGui, QtCore


class Label(QtWidgets.QLabel):
    """
    Измененный класс QLabel, умеющий обрабатывать перетаскивание
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = None
        self.allow_drag = True

    def mouseMoveEvent(self, event):
        """
        метод для перетаскивания задачи
        """
        if self.allow_drag:
            mime_data = QtCore.QMimeData()
            mime_data.setText(self.get_data())
            drag = QtGui.QDrag(self)
            drag.setMimeData(mime_data)
            drag.setPixmap(self.grab(self.rect()))
            drag.exec(QtCore.Qt.MoveAction)
            event.accept()

    def get_data(self):
        """
        метод для получения данных о задаче
        """
        return json.dumps(self.data)

    def set_drag_data(self, data):
        """
        метод для установки данных о задаче
        """
        self.data = data

    def set_drag_enabled(self, new_state: bool):
        """
        метод для разрешения/запрета перетаскивания
        """
        self.allow_drag = new_state


class TaskWidget(QtWidgets.QWidget):
    """
    Основной класс виджета задачи
    """
    widget_id = 0  # id виджета
    widget_closed = QtCore.pyqtSignal()  # сигнал закрытия окна с виджетом

    def __init__(self, text, color="#8cff7a", parent=None, id_=None, layout_id=0):
        super().__init__(parent=parent)
        self.color = color
        self.text = text
        if id_ is None:
            self.widget_id = TaskWidget.widget_id
            TaskWidget.widget_id += 1
        else:
            self.widget_id = id_
        self.attachments = None
        self.layout_id = layout_id
        self.setup_ui()

    def setup_ui(self):
        """
        главный метод для создания графического интерфейса приложения
        """
        self.main_text_label = Label(self)
        self.main_text_label.setText(self.text)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.outer_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.addWidget(self.main_text_label)
        self.color_indicator = QtWidgets.QLabel(self)
        self.color_indicator.setStyleSheet(
            f"""background: {self.color};
               border-radius: 7px;""")
        self.color_indicator.setMaximumHeight(15)
        self.main_layout.insertWidget(0, self.color_indicator)
        self.config_button = QtWidgets.QPushButton(self)
        self.config_button.setText("Configure")
        self.main_layout.addWidget(self.config_button)
        self.main_frame = QtWidgets.QFrame(self)
        self.main_frame.setLayout(self.main_layout)
        self.main_frame.setStyleSheet(""".QFrame{
            border: 1px solid black;
            border-radius: 5px;
            }""")
        self.outer_layout.addWidget(self.main_frame)
        self.update_drag_data()

    def set_attachments(self, attachments):
        """
        метод для установки обвесов задачи
        """
        self.attachments = attachments
        self.update_drag_data()
        self.add_attachments_to_label()

    def update_drag_data(self):
        """
        метод для обновления данных о задаче в главном лэйбле
        """
        self.main_text_label.set_drag_data({
            "text": self.text,
            "color": self.color,
            "id": self.widget_id,
            "attachments": self.attachments,
            "layout_id": self.layout_id,
        })

    def config_from_data(self, data):
        """
        метод для конфигурации виджета из словаря из дилогового окна
        """
        self.text = data["text"]
        self.color = data["color"]
        self.attachments = data["attachments"]
        self.main_text_label.setText(self.text)
        self.color_indicator.setStyleSheet(
            f"""background: {self.color};
               border-radius: 7px;""")
        data["id"] = self.widget_id
        data["layout_id"] = self.layout_id
        self.main_text_label.set_drag_data(data)
        if self.attachments is not None:
            self.add_attachments_to_label()

    def add_attachments_to_label(self):
        """
        метод для добавления дэдлайна, чеклиста на главный лэйбл
        """
        checklist = self.attachments.get("checklist")
        deadline = self.attachments.get("deadline")
        checklist_text = ""
        deadline_text = ""
        if checklist is not None:
            checklist_text = f"✅ {sum(el[1] for el in checklist)}/{len(checklist)}"
        if deadline is not None:
            deadline_text = deadline.split()[0]
        sep = ", " if checklist_text and deadline_text else ""
        self.main_text_label.setText(
            f"{self.main_text_label.text()}\n\n{checklist_text}{sep}{deadline_text}")

    def get_data(self):
        """
        метод для получения данных о задаче
        """
        return json.loads(self.main_text_label.get_data())

    def set_new_layout_id(self, new_id: int):
        """
        метод для установки нового id лэйаута, в котором находится виджет
        """
        self.layout_id = new_id

    def set_drag_enabled(self, new_state: bool):
        """
        метод для разрешения/запрета перетаскивания
        """
        self.main_text_label.set_drag_enabled(new_state)

    def get_id(self):
        """
        метод для получения id виджета
        """
        return self.widget_id

    @classmethod
    def set_start_id(cls, new_id):
        """
        метод для установки начального id виджетов
        """
        cls.widget_id = new_id

    def closeEvent(self, event):
        """
        метод для активации сигнала о закрытии окна с виждетом, когда он закреплен
        """
        self.widget_closed.emit()
        event.accept()
