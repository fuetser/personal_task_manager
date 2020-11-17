import datetime
from functools import partial
import os
from PyQt5 import QtWidgets, QtCore, QtGui


class NewTaskWindow(QtWidgets.QWidget):
    """
    Основной класс диалогового окна
    """

    def __init__(self, logo_filename):
        super().__init__()
        self.task_exists = False
        self.default_indicator_color = "#8cff7a"
        self.logo_filename = logo_filename
        self.setup_ui()

    def setup_ui(self):
        """
        главный метод для создания графического интерфейса приложения
        """
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_tab = MainTab(self)
        self.config_tab = ConfigureTab(self)
        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.addTab(self.main_tab, "General")
        self.tabs.addTab(self.config_tab, "Configure")
        self.main_layout.addWidget(self.tabs)
        self.setWindowTitle("Add new task")
        # установка фокуса на диалоговом окне при его вызове
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setWindowIcon(QtGui.QIcon(self.logo_filename))

    def get_parameters(self):
        """
        метод для получения информации о задаче из диалогового окна
        """
        output = {
            "text": self.main_tab.text_input.text(),
            "color": self.config_tab.indicator_color,
            "attachments": {},
        }
        if self.config_tab.datetime_selector_added:
            output["attachments"]["deadline"] = self.config_tab.datetime_select.dateTime(
            ).toString(self.config_tab.datetime_select.displayFormat())
        if self.config_tab.checklist_controls_added:
            checklist = []
            for index in range(self.config_tab.checklist_layout.count()):
                widget = self.config_tab.checklist_layout.itemAt(
                    index).widget()
                if isinstance(widget, QtWidgets.QCheckBox):
                    checklist.append(
                        (widget.text(), widget.isChecked()))
            if checklist:
                output["attachments"]["checklist"] = checklist
        if self.config_tab.file_added:
            output["attachments"]["file"] = self.config_tab.file_path
        if len(output["attachments"]) == 0:
            output["attachments"] = None
        return output

    def reset_fields(self, reset_flags=True):
        """
        метод для приведения всех полей к дефолтному состоянию
        """
        self.config_tab.color_indicator.setStyleSheet(
            f"""background: {self.default_indicator_color};
               border-radius: 7px;""")
        self.config_tab.indicator_color = self.default_indicator_color
        self.main_tab.text_input.setText("")
        self.config_tab.hide_attachments(reset_flags)
        self.tabs.setCurrentIndex(0)
        self.task_exists = False
        self.main_tab.done_button.setText("Add task")
        self.main_tab.remove_delete_button()
        self.main_tab.remove_pin_button()

    def fill_from_task(self, text: str, color: str, attachments):
        """
        метод для установки состояния полей из строки из базы данных
        """
        self.task_exists = True
        self.config_tab.attachments_showed = attachments is None
        self.config_tab.select_attachments()
        self.main_tab.text_input.setText(text)
        self.main_tab.done_button.setText("Save task")
        self.config_tab.indicator_color = color
        self.config_tab.color_indicator.setStyleSheet(
            f"""background: {color};
               border-radius: 7px;""")
        self.setWindowTitle("Change task")
        if attachments is not None:
            self.add_attachments(attachments)
        self.main_tab.add_delete_button()
        self.main_tab.add_pin_button()

    def add_attachments(self, attachments):
        """
        метод для добавления обвесов при вызове диалога для изменения задачи
        """
        deadline = attachments.get("deadline")
        checklist = attachments.get("checklist")
        file = attachments.get("file")
        if deadline is not None:
            self.config_tab.select_deadline(deadline)
            self.config_tab.attachments_checkboxes[0].setChecked(True)
        if checklist:
            self.config_tab.add_checklist(checklist)
            self.config_tab.attachments_checkboxes[1].setChecked(True)
        if file:
            self.config_tab.add_file(file)
            self.config_tab.attachments_checkboxes[2].setChecked(True)

    def closeEvent(self, event):
        """
        метод для приведения полей к дефолтному состоянию при закрытии диалога
        """
        self.reset_fields()
        event.accept()

    def is_existing_task(self):
        """
        метод для получения информации о том, существует ли такая задача
        """
        return self.task_exists

    def keyPressEvent(self, event):
        """
        метод для обработки нажатий на кнопки
        """
        # добавление задачи по нажатию на кнопку Enter
        if event.key() == QtCore.Qt.Key_Return and self.tabs.currentIndex() == 0:
            self.main_tab.done_button.clicked.emit()
        # добавление элемента чеклиста по нажатию на кнопку Enter
        elif event.key() == QtCore.Qt.Key_Return and self.tabs.currentIndex() == 1:
            if self.config_tab.checklist_controls_added:
                self.config_tab.checklist_add_button.clicked.emit()


class ConfigureTab(QtWidgets.QWidget):
    """
    Класс для создания вкладки Configure
    """

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.indicator_color = "#8cff7a"
        self.attachments_fields = ("Deadline", "Check list", "File")
        self.attachments_showed = False
        self.datetime_selector_added = False
        self.checklist_controls_added = False
        self.file_added = False
        self.setup_ui()

    def setup_ui(self):
        """
        главный метод для создания графического интерфейса приложения
        """
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.select_color_button = QtWidgets.QPushButton("Select color", self)
        self.add_attachments_button = QtWidgets.QPushButton(
            "Add attachments", self)
        self.color_indicator = QtWidgets.QLabel(self)
        self.color_indicator.setStyleSheet(
            f"""background: {self.indicator_color};
            border-radius: 7px;""")
        self.color_indicator.setMaximumHeight(15)
        self.main_layout.addWidget(self.color_indicator)
        self.main_layout.addWidget(self.select_color_button)
        self.main_layout.addWidget(self.add_attachments_button)
        self.add_attachments_button.clicked.connect(self.select_attachments)
        self.select_color_button.clicked.connect(self.select_color)

    def select_color(self):
        """
        метод для показа диалога выбора цвета
        """
        new_color = QtWidgets.QColorDialog.getColor()
        if new_color.isValid():
            self.indicator_color = new_color.name()
            self.color_indicator.setStyleSheet(
                f"""background: {self.indicator_color};
                   border-radius: 7px;""")

    def select_attachments(self):
        """
        метод для отображения чекбоксов для выбора обвесов
        """
        if not self.attachments_showed:
            self.attachments_showed = True
            self.scroll_area = QtWidgets.QScrollArea(self)
            self.scroll_area.setWidgetResizable(True)
            self.scroll_inner = QtWidgets.QWidget()
            self.attachments_layout = QtWidgets.QVBoxLayout()
            self.scroll_inner.setLayout(self.attachments_layout)
            self.scroll_area.setWidget(self.scroll_inner)
            self.attachments_checkboxes = [QtWidgets.QCheckBox(
                field, self) for field in self.attachments_fields]
            self.main_layout.addWidget(self.scroll_area)
            for checkbox in self.attachments_checkboxes:
                checkbox.stateChanged.connect(self.show_attachments)
                checkbox.setStyleSheet("text-decoration: underline;")
                self.attachments_layout.addWidget(checkbox)
        else:
            self.hide_attachments()

    def hide_attachments(self, reset_flags=True):
        """
        метод для удаления виджетов выбора обвесов
        """
        if reset_flags:
            self.attachments_showed = False
            self.datetime_selector_added = False
            self.checklist_controls_added = False
            self.file_added = False
        for index in range(self.main_layout.count()):
            if index > 2:
                widget = self.main_layout.itemAt(index).widget()
                layout = self.main_layout.itemAt(index).layout()
                if widget is not None:
                    widget.deleteLater()
                elif layout is not None:
                    for ind in range(layout.count()):
                        layout.itemAt(ind).widget().deleteLater()
                    layout.deleteLater()

    def show_attachments(self):
        """
        метод для отображения/удаления обвеса в зависимости от состояния чекбокса
        """
        if self.attachments_showed:
            if self.attachments_checkboxes[0].isChecked():
                self.select_deadline()
            else:
                self.delete_deadline()

            if self.attachments_checkboxes[1].isChecked():
                self.add_checklist()
            else:
                self.delete_checklist()

            if self.attachments_checkboxes[2].isChecked():
                self.add_file()
            else:
                self.delete_file()

    def select_deadline(self, date=None):
        """
        метод для добавления поля выбора дэдлайна
        """
        if not self.datetime_selector_added:
            self.datetime_selector_added = True
            self.datetime_select = QtWidgets.QDateTimeEdit(self)
            self.datetime_select.setCalendarPopup(True)
            if date is None:
                self.datetime_select.setDate(QtCore.QDate(
                    datetime.datetime.now() + datetime.timedelta(days=7)))
                self.datetime_select.setTime(QtCore.QTime.currentTime())
            else:
                self.datetime_select.setDateTime(QtCore.QDateTime(
                    datetime.datetime.strptime(date, "%d.%m.%Y %H:%M")))
            self.attachments_layout.insertWidget(1, self.datetime_select)

    def add_checklist(self, checklist=None):
        """
        метод для добавления чеклиста
        """
        if not self.checklist_controls_added:
            self.checklist_controls_added = True
            self.checklist_insert_index = 0
            self.add_checklist_controlls()
            if checklist is not None:
                self.add_checklist_from_task(checklist)
            self.attachments_layout.insertLayout(
                2 + int(self.datetime_selector_added), self.checklist_layout)

    def add_checklist_controlls(self):
        """
        метод для добавления виджетов для изменения чеклиста
        """
        self.checklist_layout = QtWidgets.QVBoxLayout()
        self.checklist_input = QtWidgets.QLineEdit(self)
        self.checklist_layout.addWidget(self.checklist_input)
        self.checklist_add_button = QtWidgets.QPushButton("Add", self)
        self.checklist_delete_button = QtWidgets.QPushButton("Delete", self)
        self.checklist_add_button.clicked.connect(self.add_checklist_item)
        self.checklist_delete_button.clicked.connect(
            self.delete_checklist_items)
        self.checklist_layout.addWidget(self.checklist_add_button)
        self.checklist_layout.addWidget(self.checklist_delete_button)

    def add_checklist_item(self):
        """
        метод для добавления пункта чеклиста
        """
        text = self.checklist_input.text()
        if text:
            self.checklist_layout.insertWidget(
                self.checklist_insert_index, QtWidgets.QCheckBox(text, self))
            self.checklist_insert_index += 1
            self.checklist_input.setText("")

    def add_checklist_from_task(self, checklist):
        """
        метод для добавления существующего чеклиста
        """
        for text, checked in checklist:
            widget = QtWidgets.QCheckBox(text, self)
            widget.setChecked(checked)
            self.checklist_layout.insertWidget(
                self.checklist_insert_index, widget)
            self.checklist_insert_index += 1

    def delete_checklist_items(self):
        """
        метод для удаления выбранных элементов чеклиста
        """
        for index in range(self.checklist_layout.count()):
            widget = self.checklist_layout.itemAt(index).widget()
            if isinstance(widget, QtWidgets.QCheckBox) and widget.isChecked():
                self.checklist_layout.itemAt(index).widget().deleteLater()
                self.checklist_insert_index -= 1

    def delete_deadline(self):
        """
        метод для удаления поля выбора дэдлайна
        """
        for index in range(self.attachments_layout.count()):
            if isinstance(self.attachments_layout.itemAt(
                    index).widget(), QtWidgets.QDateTimeEdit):
                self.attachments_layout.itemAt(index).widget().deleteLater()
                break
        self.datetime_selector_added = False

    def delete_checklist(self):
        """
        метод для удаления чеклиста
        """
        if hasattr(self, "checklist_layout"):
            try:
                for index in range(self.checklist_layout.count()):
                    self.checklist_layout.itemAt(
                        index).widget().deleteLater()
                self.checklist_layout.deleteLater()
                self.checklist_controls_added = False
            except RuntimeError:
                pass

    def add_file(self, file=None):
        """
        метод для добавления файла к задаче
        """
        if not self.file_added:
            self.file_added = True
            if file is None:
                self.file_path = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Select file", "", "All files (*.*)")[0]
            else:
                self.file_path = file
            if self.file_path:
                file_name = self.file_path.split("/")[-1]
                self.file_button = QtWidgets.QPushButton(file_name, self)
                self.file_button.clicked.connect(
                    partial(self.run_file, self.file_path))
                self.attachments_layout.addWidget(self.file_button)
            else:
                self.attachments_checkboxes[2].setChecked(False)
                self.file_added = False

    def run_file(self, file_path: str):
        """
        метод для запуска добавленного файла
        """
        try:
            os.startfile(file_path)
        except Exception as err:
            QtWidgets.QMessageBox.warning(
                self, "Exception occured",
                f"Exception occured while running the file.\n({err})",
                QtWidgets.QMessageBox.Ok)

    def delete_file(self):
        """
        метод для удаления файла
        """
        if self.file_added:
            self.attachments_layout.itemAt(
                self.attachments_layout.count() - 1).widget().deleteLater()
            self.file_path = ""
            self.file_name = ""
            self.file_added = False


class MainTab(QtWidgets.QWidget):
    """
    Класс для создания вкладки General
    """

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.delete_button_added = False
        self.pin_button_added = False
        self.setup_ui()

    def setup_ui(self):
        """
        главный метод для создания графического интерфейса приложения
        """
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.text_input = QtWidgets.QLineEdit(self)
        self.done_button = QtWidgets.QPushButton("Add task", self)
        self.main_layout.addWidget(self.text_input)
        self.main_layout.addWidget(self.done_button)

    def add_delete_button(self):
        """
        метод для добавления кнопки удаления задачи
        """
        if not self.delete_button_added:
            self.delete_button_added = True
            self.delete_button = QtWidgets.QPushButton("Delete task", self)
            self.main_layout.addWidget(self.delete_button)

    def remove_delete_button(self):
        """
        метод для удаления кнопки удаления задачи
        """
        if self.delete_button_added:
            self.delete_button_added = False
            self.main_layout.itemAt(
                self.main_layout.count() - 2).widget().deleteLater()

    def add_pin_button(self):
        """
        метод для добавления кнопки закрепления задачи
        """
        if not self.pin_button_added:
            self.pin_button_added = True
            self.pin_button = QtWidgets.QPushButton("Pin task", self)
            self.main_layout.addWidget(self.pin_button)

    def remove_pin_button(self):
        """
        метод для удаления кнопки закрепления задачи
        """
        if self.pin_button_added:
            self.pin_button_added = False
            self.main_layout.itemAt(
                self.main_layout.count() - 1).widget().deleteLater()
