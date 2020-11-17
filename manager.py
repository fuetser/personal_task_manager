from functools import partial
import json
from new_task_window import NewTaskWindow
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import pyqtgraph.exporters
import sqlite3
import sys
from task_widget import TaskWidget


class GroupBox(QtWidgets.QGroupBox):
    """
    Модифицированный класс групбокса, который умеет обрабатывать drag event
    """
    box_id = 0  # id групбокса
    item_added = QtCore.pyqtSignal()  # сигнал добавления нового элемента

    def __init__(self, title=""):
        super().__init__(title)
        self.setAcceptDrops(True)
        self.task_data = None
        self.box_id = GroupBox.box_id
        GroupBox.box_id += 1

    def dragEnterEvent(self, event):
        """
        метод для обработки drag event, в зависимости от наличия текста
        """
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        метод для распаковки данных перетащенного виджета и активации сигнала
        о добавлении нового элемента в групбокс
        """
        self.task_data = json.loads(event.mimeData().text())
        self.item_added.emit()

    def get_drop_data(self):
        """
        метод для получения данных о добавленном видежете
        """
        return self.task_data


class MainWindow(QtWidgets.QMainWindow):
    """
    Основной класс приложения, обрабатывающий все взаимодействия с ним
    """

    def __init__(self, db_name, logo_filename):
        super().__init__()
        self.logo_filename = logo_filename
        self.db_name = db_name  # название базы данных
        self.db_connection = sqlite3.connect(self.db_name)
        self.db_cursor = self.db_connection.cursor()
        self.current_table_id = 1  # id текущей таблицы с заданиями
        # список действий из меню "Select table" для изменения их названий
        self.tables_actions = []
        self.create_database()
        self.set_start_task_id()
        self.update_tables_count()
        # названия полей для задач
        self.fields = ("Resources", "To Do", "Doing", "Done")
        self.FIELDS_AMOUNT = len(self.fields)  # количество полей в программе
        # id лэйаута, в который нужно добавить новый созданный виджет
        self.active_layout = 0
        self.pinned_tasks_ids = []
        self.active_task = None
        self.pinned_task = None
        self.app_running = True
        self.setup_ui()
        self.show_tasks_from_database()

    def setup_ui(self):
        """
        главный метод для создания графического интерфейса приложения
        """
        # создание диалогового окна для создания/изменения задачи
        self.new_task_window = NewTaskWindow(self.logo_filename)
        self.new_task_window.main_tab.done_button.clicked.connect(
            self.handle_task_button)  # подключение кнопки диалога
        self.centralwidget = QtWidgets.QWidget(self)
        self.main_layout = QtWidgets.QHBoxLayout(self.centralwidget)
        # создание внутренних лэйаутов для групбоксов
        self.scroll_layouts = [QtWidgets.QVBoxLayout()
                               for _ in range(self.FIELDS_AMOUNT)]
        # создание лэйаутов, содержащих групбокс и кнопку добавления задачи
        self.inner_layouts = [QtWidgets.QVBoxLayout()
                              for _ in range(self.FIELDS_AMOUNT)]
        self.add_task_buttons = [QtWidgets.QPushButton(
            "Add new") for _ in range(self.FIELDS_AMOUNT)]
        self.groupboxes = [GroupBox(field) for field in self.fields]
        # подключение кнопок добавления задач и добавление их в лэйауты
        for index, button in enumerate(self.add_task_buttons):
            button.clicked.connect(partial(self.show_new_task_dialog, index))
            self.inner_layouts[index].addWidget(button)
        # настройка лэйаутов и добавление их в групбоксы
        for index, layout in enumerate(self.inner_layouts):
            self.scroll_layouts[index].setContentsMargins(0, 0, 0, 0)
            self.scroll_layouts[index].setSpacing(0)
            self.groupboxes[index].setLayout(layout)
            self.groupboxes[index].item_added.connect(
                partial(self.add_draged_widget, index))
            self.main_layout.addWidget(self.groupboxes[index])

        self.setWindowIcon(QtGui.QIcon(self.logo_filename))
        self.setCentralWidget(self.centralwidget)
        self.setup_scroll_areas()
        self.setup_help_messagbox()
        self.setup_menubar()
        self.setWindowTitle("Task Manager")

    def setup_menubar(self):
        """
        метод для создания и настройки строки меню
        """
        self.menubar = self.menuBar()
        self.menu_tasks = self.menubar.addMenu("Tasks")
        self.menu_tables = self.menubar.addMenu("Tables")
        show_help_info_action = QtWidgets.QAction("Help", self)
        show_help_info_action.triggered.connect(self.help_messagebox.show)
        self.menubar.addAction(show_help_info_action)
        self.setup_tasks_menu()
        self.setup_tables_menu()

    def setup_tasks_menu(self):
        """
        метод для настройки меню Tasks
        """
        add_task_action = QtWidgets.QAction("Add new", self)
        add_task_action.setShortcut("Ctrl+N")
        add_task_action.triggered.connect(self.show_new_task_dialog)
        self.menu_tasks.addAction(add_task_action)
        # создание подменю
        for title, callback in zip(("Export task", "Import task", "Clear task list"),
                                   (self.export_task, self.import_task,
                                    self.confirm_clear_tasks_list)):
            self.setup_submenu(self.menu_tasks, title,
                               tuple(enumerate(self.fields)), callback)

    def setup_tables_menu(self):
        """
        метод для настройки меню Tables
        """
        add_new_table_action = QtWidgets.QAction("Add new table", self)
        add_new_table_action.triggered.connect(self.add_new_table)
        add_new_table_action.setShortcut("Ctrl+Shift+N")
        plot_tables_action = QtWidgets.QAction("Save tables plot", self)
        plot_tables_action.triggered.connect(self.plot_tables_statistics)
        self.menu_tables.addAction(add_new_table_action)
        # получение информации о всех существующих таблицах
        tables = self.db_cursor.execute("SELECT * FROM tables").fetchall()
        # создание подменю
        for title, callback in zip(
            ("Select table", "Delete table", "Change table title"),
                (self.load_table, self.delete_table, self.change_table_name)):
            self.setup_submenu(self.menu_tables, title,
                               tables, callback, save_action=title == "Select table")
        self.menu_tables.addAction(plot_tables_action)

    def setup_submenu(self, parent_menu: QtWidgets.QMenu, title: str,
                      tables: list, callback, save_action=False):
        """
        метод для создания подменю и сохранения действий из меню "Select table"
        args(
            parent_menu: QtWidgets.QMenu - меню, в которое добавляется подменю,
            title: str - названия действия,
            tables: list - список вида [(int, str), (int, str)],
            callback: func - функция, срабатывающая при выборе пункта подменю,
            save_action: bool - нужно ли сохранять действия в список tables_actions
        )
        """
        submenu = QtWidgets.QMenu(title, self)
        for id_, text in tables:
            action = QtWidgets.QAction(text, self)
            action.triggered.connect(partial(callback, id_))
            submenu.addAction(action)
            if save_action:
                self.tables_actions.append(action)
        parent_menu.addMenu(submenu)

    def setup_scroll_areas(self):
        """
        метод для создания и настройки полей прокрутки
        """
        self.scroll_areas = [QtWidgets.QScrollArea(
            self.centralwidget) for _ in range(self.FIELDS_AMOUNT)]
        self.scroll_inners = [QtWidgets.QWidget()
                              for _ in range(self.FIELDS_AMOUNT)]

        for index, area in enumerate(self.scroll_areas):
            self.scroll_inners[index].setLayout(self.scroll_layouts[index])
            area.setWidgetResizable(True)
            area.setMinimumWidth(175)
            area.setWidget(self.scroll_inners[index])
            self.inner_layouts[index].addWidget(area)

    def setup_help_messagbox(self):
        """
        метод для создания и настройки help диалога
        """
        self.help_messagebox = QtWidgets.QPlainTextEdit()
        try:
            with open("help_text", "r", encoding="u8") as f:
                content = f.read()
        except Exception as err:
            content = f"Unable to load help text.\n{err}"
        self.help_messagebox.setPlainText(content)
        self.help_messagebox.setReadOnly(True)
        self.help_messagebox.setWindowTitle("Help information")
        # установка фокуса на диалог
        self.help_messagebox.setWindowModality(QtCore.Qt.ApplicationModal)
        self.help_messagebox.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.help_messagebox.setWindowIcon(QtGui.QIcon(self.logo_filename))

    def show_new_task_dialog(self, layout: int):
        """
        метод для показа дилога добавления/изменения задачи
        """
        self.new_task_window.show()
        self.active_layout = layout

    def add_task(self, text="", target_layout_id=0, attachments=None, from_data=None, **kwargs):
        """
        метод для создания и добавления задачи в заданый лэйаут
        args(
            text: str - текст, отображаемый на виджете,
            target_layout_id: int - id лэйаута, в который нужно добавить виджет,
            attachments: dict - словарь с описанием обвесов задачи,
            from_data: list - список, содержащий данные строки из базы данных,
            kwargs: dict - дополнительные аргументы для создания виджета задачи
        )
        """
        task = TaskWidget(text, layout_id=target_layout_id, **kwargs)
        if from_data is not None:
            task.config_from_data(from_data)
        if attachments is not None:
            task.set_attachments(attachments)
        # добавление заадчи в базу данных, если она только что создана
        # при перетаскивании передается аргумент id_: int - id задачи
        if kwargs.get("id_") is None:
            self.add_task_to_database(task.get_data())
        task.config_button.clicked.connect(
            partial(self.configure_task, task))
        self.scroll_layouts[target_layout_id].addWidget(task)

    def handle_task_button(self):
        """
        метод для обработки нажатия на кнопку в диалоговом окне
        """
        # если задача уже существует, то она обновляется в базе данных
        if self.new_task_window.is_existing_task():
            self.update_task()
        else:
            self.add_task_from_dialog()

    def add_task_from_dialog(self):
        """
        метод для создания новой задачи из диалогового окна
        """
        data = self.new_task_window.get_parameters()
        if data["text"]:
            self.add_task(text=data["text"], target_layout_id=self.active_layout,
                          parent=self.centralwidget, color=data["color"],
                          attachments=data["attachments"])
            self.new_task_window.reset_fields()
            self.new_task_window.close()

    def update_task(self, pinned_task=None):
        """
        метод для обновления задачи
        """
        data = self.new_task_window.get_parameters()
        if pinned_task is not None:
            self.active_task = pinned_task
        if data["text"]:
            self.active_task.config_from_data(data)
            self.update_task_in_database(self.active_task.get_data())
            self.new_task_window.reset_fields()
            self.new_task_window.close()

    def configure_task(self, task: TaskWidget):
        """
        метод для изменения задачи в диалоговом окне
        """
        self.active_task = task
        self.new_task_window.reset_fields(reset_flags=False)
        # подготовка полей диалогового окна
        self.new_task_window.fill_from_task(
            task.text, task.color, task.attachments)
        # подключение кнопок удаления и закрепления задачи
        self.new_task_window.main_tab.delete_button.clicked.connect(
            self.delete_task)
        self.new_task_window.main_tab.pin_button.clicked.connect(
            partial(self.pin_task, task))
        self.new_task_window.show()

    def delete_task(self):
        responce = QtWidgets.QMessageBox.warning(
            None, "Warning", "Task will be permanently deleted.\nContinue?",
            QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Cancel)
        if responce == QtWidgets.QMessageBox.Ok:
            self.delete_task_from_database(self.active_task.get_id())
            self.delete_copied_widget(self.active_task.get_id())
            if self.active_task.get_id() in self.pinned_tasks_ids:
                self.active_task.close()
            self.new_task_window.close()

    def export_task(self, layout_id: int):
        """
        метод для экспорта задачи из заданного лэйаута
        """
        text = self.get_text_for_export_dialog(layout_id)
        if text:
            # получение задачи для экспорта
            item, accepted = QtWidgets.QInputDialog.getItem(self, "Select task",
                                                            "Select task you want to export:",
                                                            text, 0, False)
            if accepted:
                self.export_selected_task(layout_id, text.index(item))
        else:
            # показ предупреждения, если в лэйауте нет виджетов
            QtWidgets.QMessageBox.warning(
                self, "List is empty",
                "You can't select widget from an empty list.",
                QtWidgets.QMessageBox.Ok)

    def get_text_for_export_dialog(self, layout_id: int):
        """
        метод для получения списка названий виджетов без повторений
        """
        widgets = [self.scroll_layouts[layout_id].itemAt(
            index).widget() for index in range(
            self.scroll_layouts[layout_id].count())]
        text = []
        for widget in widgets:
            if widget.text not in text:
                text.append(widget.text)
            else:
                index = 1
                new_text = f"{widget.text}({index})"
                while new_text in text:
                    index += 1
                    new_text = f"{widget.text}({index})"
                else:
                    text.append(new_text)
        return text

    def export_selected_task(self, layout_id: int, task_id: int):
        """
        метод для сохранения файла с выбранной для экспорта задачей
        """
        file_path = QtWidgets.QFileDialog.getSaveFileName(
            None, "Save task", "", "Json (*.json)")[0]
        if file_path:
            widget_data = self.scroll_layouts[layout_id].itemAt(
                task_id).widget().get_data()
            try:
                with open(file_path, "w", encoding="u8") as f:
                    json.dump(widget_data, f)
            except Exception as err:
                QtWidgets.QMessageBox.warning(
                    self, "Exception occured",
                    f"Exception occured while exporting the file.\n({err})",
                    QtWidgets.QMessageBox.Ok)

    def import_task(self, layout_id: int):
        """
        метод для импорта задачи в заданный лэйаут
        """
        file_path = QtWidgets.QFileDialog.getOpenFileName(
            None, "Save task", "", "Json (*.json)")[0]
        if file_path:
            try:
                with open(file_path, "r", encoding="u8") as f:
                    task_data = json.load(f)
                self.add_task(target_layout_id=layout_id, from_data=task_data)
            except Exception:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid file",
                    "You have selected invalid task file.",
                    QtWidgets.QMessageBox.Ok)

    def delete_copied_widget(self, target_id: int):
        """
        метод для удаления виджета задачи после перетаскивания из стартового лэйаута
        """
        for layout in self.scroll_layouts:
            for index in range(layout.count()):
                widget = layout.itemAt(index).widget()
                if widget.get_id() == target_id:
                    widget.deleteLater()
                    return

    def create_database(self):
        """
        метод для создания таблиц в базе данных, если их не существует
        """
        self.db_cursor.executescript("""
            CREATE TABLE IF NOT EXISTS tables(
                id INTEGER PRIMARY KEY,
                title TEXT);
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER,
                comment TEXT,
                color TEXT,
                attachments TEXT,
                table_id INTEGER,
                layout_id INTEGER,
                FOREIGN KEY(table_id) REFERENCES tables(id))""")
        # создание таблицы по умолчанию, если не существует других
        if not len(self.db_cursor.execute("SELECT * FROM tables").fetchall()):
            self.db_cursor.execute(
                """INSERT INTO tables(id, title)
                    VALUES (NULL, 'default')""")
        self.db_connection.commit()

    def add_task_to_database(self, task_data):
        """
        метод для добавления задачи в базу данных
        """
        # конвертация словаря словаря с обвесами в формат json
        if task_data["attachments"] is not None:
            task_data["attachments"] = json.dumps(task_data["attachments"])
        # id таблицы, в которой находится задача
        task_data["table_id"] = self.current_table_id
        task_data["layout_id"] = self.active_layout
        self.db_cursor.execute("""INSERT INTO tasks VALUES
            (:id, :text, :color, :attachments, :table_id, :layout_id)""",
                               task_data)
        self.db_connection.commit()

    def set_start_task_id(self):
        """
        метод для установки начального id для виджетов задач
        """
        try:
            new_id = self.db_cursor.execute(
                "SELECT id FROM tasks ORDER BY id").fetchall()[-1][0] + 1
        except IndexError:
            new_id = 0
        finally:
            TaskWidget.set_start_id(new_id)

    def show_tasks_from_database(self):
        """
        метод для загрузки задач из базы данных
        """
        tasks = self.db_cursor.execute("""SELECT * FROM tasks
            WHERE table_id = ?""", (self.current_table_id,))
        self.mark_selected_table()
        for task in tasks:
            if task[0] not in self.pinned_tasks_ids:
                self.add_task_from_database(task)

    def add_task_from_database(self, task_data):
        """
        метод для создания задачи из информации из строки базы данных
        """
        id_, text, color, attachments, table_id, layout_id = task_data
        if attachments is not None:
            attachments = json.loads(attachments)
        self.add_task(text=text, target_layout_id=layout_id,
                      attachments=attachments, color=color,
                      parent=self.centralwidget, id_=id_)

    def update_task_in_database(self, task_data):
        """
        метод для обновления информации о задаче в базе данных
        """
        if task_data["attachments"] is not None:
            task_data["attachments"] = json.dumps(task_data["attachments"])
        task_data["table_id"] = self.current_table_id
        self.db_cursor.execute("""UPDATE tasks SET
            id = id,
            comment = :text,
            color = :color,
            attachments = :attachments,
            table_id = :table_id,
            layout_id = :layout_id
            WHERE id = :id""", task_data)
        self.db_connection.commit()

    def delete_task_from_database(self, task_id: int):
        """
        метод для удаления задачи из базы данных
        """
        self.db_cursor.execute("""DELETE FROM tasks
            WHERE id = ?""", (task_id,))
        self.db_connection.commit()

    def add_draged_widget(self, groupbox_id: int):
        """
        метод для обработки перетаскивания виджетов
        """
        # получение информации о виджете
        task_data = self.groupboxes[groupbox_id].get_drop_data()
        # удаление виджета в стартовом лэйауте
        self.delete_copied_widget(task_data["id"])
        task = TaskWidget(task_data["text"], task_data["color"],
                          id_=task_data["id"], layout_id=groupbox_id)
        if task_data["attachments"] is not None:
            task.set_attachments(task_data["attachments"])
        task.config_button.clicked.connect(partial(self.configure_task, task))
        self.scroll_layouts[groupbox_id].addWidget(task)
        # обновление id лэйаута у задачи в базе данных
        self.db_cursor.execute("""UPDATE tasks SET
            id = id,
            comment = comment,
            color = color,
            attachments = attachments,
            table_id = table_id,
            layout_id = ?
            WHERE id = ?""", (groupbox_id, task_data["id"]))
        self.db_connection.commit()

    def clear_tasks_list(self, *args, delete_from_database=False):
        """
        метод для очистки списка задач и удаления их из базы данных
        """
        for layout_id in args:
            layout = self.scroll_layouts[layout_id]
            for index in range(layout.count()):
                widget = layout.itemAt(index).widget()
                if delete_from_database:
                    self.delete_task_from_database(widget.get_id())
                widget.deleteLater()

    def confirm_clear_tasks_list(self, list_id: int):
        """
        метод для показа диалога подтверждения очистики списка задач
        """
        # проверка на наличие задач с выбранном списке
        enough_tasks_in_list = self.scroll_layouts[list_id].count() > 0
        warning_message = f"All tasks from {self.fields[list_id]} list wil be deleted.\nContinue?"
        if not enough_tasks_in_list:
            warning_message = "You can't clear empty list."
        responce = QtWidgets.QMessageBox.warning(None, "Warning",
                                                 warning_message,
                                                 QtWidgets.QMessageBox.Ok,
                                                 QtWidgets.QMessageBox.Cancel)
        if responce == QtWidgets.QMessageBox.Ok and enough_tasks_in_list:
            self.clear_tasks_list(list_id, delete_from_database=True)

    def load_table(self, table_id: int):
        """
        метод для отображения выбранной таблицы
        """
        self.current_table_id = table_id
        self.clear_tasks_list(0, 1, 2, 3)
        self.show_tasks_from_database()

    def add_new_table(self):
        """
        метод для создания новой таблицы
        """
        text, accepted = QtWidgets.QInputDialog.getText(
            self, "Crete new table", "Enter table title:")
        if accepted and text:
            self.db_cursor.execute("""INSERT INTO tables(id, title)
                VALUES (NULL, ?)""", (text,))
            self.db_connection.commit()
            self.update_menubar()
            self.update_tables_count()

    def delete_table(self, table_id: int):
        """
        метод для удаления таблицы
        """
        if self.confirm_deleting_table(table_id):
            query = f"""
            DELETE FROM tables WHERE id = {table_id};
            DELETE FROM tasks WHERE table_id = {table_id}"""
            self.db_cursor.executescript(query)
            if self.current_table_id == table_id:
                self.load_table(1)
                self.current_table_id = 1
            self.db_connection.commit()
            self.update_menubar()
            self.update_tables_count()

    def confirm_deleting_table(self, table_id: int):
        """
        метод для показа диалога подтверждения удаления таблицы
        """
        # проверка, достаточно ли осталось таблиц для удаления
        enough_tables_left = self.tables_count > 1
        warning_message = "You can't delete the last table."
        if enough_tables_left:
            table_name = self.db_cursor.execute("""SELECT title FROM tables
                WHERE id = ?""", (table_id,)).fetchone()[0]
            warning_message = f"Table '{table_name}' will be permanently deleted.\nContinue?"
        responce = QtWidgets.QMessageBox.warning(
            None, "Warning",
            warning_message,
            QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Cancel)
        return responce == QtWidgets.QMessageBox.Ok and enough_tables_left

    def change_table_name(self, table_id: int):
        """
        метод для изменения названия таблицы
        """
        text, accepted = QtWidgets.QInputDialog.getText(
            self, "Change table name", "Enter new table title:")
        if accepted and text:
            self.db_cursor.execute("""UPDATE tables SET
                title = ? WHERE id = ?""", (text, table_id))
            self.db_connection.commit()
            self.update_menubar()

    def update_tables_count(self):
        """
        метод для обновления количества таблиц
        """
        self.tables_count = len(self.db_cursor.execute(
            "SELECT * FROM tables").fetchall())

    def mark_selected_table(self):
        """
        метод для отметки выбранной таблицы в подменю Select table
        """
        for index, action in enumerate(self.tables_actions):
            new_text = action.text().replace(" ✓", "")
            if index == self.current_table_id - 1:
                action.setText(f"{new_text} ✓")
            else:
                action.setText(new_text)

    def update_menubar(self):
        """
        метод для очистки и заполнения меню бара
        """
        self.tables_actions.clear()
        self.menubar.clear()
        self.setup_menubar()
        self.mark_selected_table()

    def plot_tables_statistics(self):
        """
        метод для сохранения графика количества задач
        """
        if self.tables_count > 1:
            file_path = QtWidgets.QFileDialog.getSaveFileName(
                None, "Save plot image", "", "Png (*.png)")[0]
            if file_path:
                self.create_plot(file_path)
        else:
            QtWidgets.QMessageBox.warning(
                None, "Warning", "Not enough tables to plot.\nAt least 2 required.")

    def create_plot(self, file_path: str):
        """
        метод для создания и сохранения графика количества задач
        """
        tables = self.db_cursor.execute("SELECT * FROM tables").fetchall()
        widgets_count = {el[0]: 0 for el in tables}
        for id_, name in tables:
            widgets_count[id_] = len(self.db_cursor.execute(
                "SELECT * FROM tasks WHERE table_id = ?", (id_,)).fetchall())
        plt = pg.plot(tuple(widgets_count.keys()),
                      tuple(widgets_count.values()))
        plt.setLabel("left", "Amount of widgets")
        plt.setLabel("bottom", "Table id")
        exporter = pg.exporters.ImageExporter(plt.plotItem)
        exporter.export(file_path)

    def pin_task(self, task: TaskWidget):
        """
        метод для закрепления задачи поверх всех окон
        """
        self.pinned_task = task
        self.update_task(self.pinned_task)
        self.pinned_task.setParent(None)
        self.pinned_task.setWindowTitle("Pinned task")
        self.pinned_task.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.pinned_task.set_drag_enabled(False)
        self.pinned_task.widget_closed.connect(partial(self.unpin_task, task))
        self.pinned_tasks_ids.append(task.get_id())
        self.new_task_window.close()
        self.pinned_task.setWindowIcon(QtGui.QIcon(self.logo_filename))
        self.pinned_task.show()
        self.pinned_task.move(200, 200)

    def unpin_task(self, task: TaskWidget):
        """
        метод для удаления закрепленной задачи
        """
        if self.app_running:
            task_data = task.get_data()
            table_id = self.db_cursor.execute(
                "SELECT table_id FROM tasks WHERE id = ?",
                (task_data["id"],)).fetchone()
            table_id = table_id[0] if table_id is not None else -1
            task.setParent(self.centralwidget)
            if task_data["id"] in self.pinned_tasks_ids:
                self.pinned_tasks_ids.remove(task_data["id"])
            if table_id == self.current_table_id:
                task.set_drag_enabled(True)
                self.scroll_layouts[task_data["layout_id"]].addWidget(task)

    def closeEvent(self, event):
        """
        метод для обработки события закрытия приложения
        """
        self.app_running = False
        self.db_connection.close()
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow("task_manager.db", "logo.png")
    window.show()
    sys.exit(app.exec())
