# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
#
# This file is part of Furious.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from Furious.Core.Core import XrayCore, Hysteria
from Furious.Core.TorRelay import TorRelay
from Furious.Utility.Constants import APP, APPLICATION_NAME, TOR_FAQ_LABEL


class Translatable:
    Object = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.translatable = True

        Translatable.Object.append(self)

    def retranslate(self):
        raise NotImplementedError

    @staticmethod
    def retranslateAll():
        for ob in Translatable.Object:
            assert isinstance(ob, Translatable)

            if ob.translatable:
                ob.retranslate()


class Translator:
    def __init__(self):
        super().__init__()

        self.translation = dict()
        self.dictEnglish = dict()

    def install(self, translation):
        self.translation = translation

        for key, value in translation.items():
            # English -> English
            value['EN'] = key

            for lang, text in value.items():
                self.dictEnglish[text] = key

        # English -> English
        self.dictEnglish.update(dict(list((key, key) for key in translation.keys())))

    def translate(self, source, locale):
        if source in NO_TRANSLATION_DICT:
            return source
        else:
            return self.translation[self.dictEnglish[source]][locale]


_trans = Translator()


def installTranslation(translation):
    _trans.install(translation)


def gettext(source, locale=None):
    if locale is None:
        assert APP() is not None

        return _trans.translate(source, APP().Language)
    else:
        assert locale in list(LANGUAGE_TO_ABBR.values())

        return _trans.translate(source, locale)


LANGUAGE_TO_ABBR = {
    'English': 'EN',
    'Español': 'ES',
    '简体中文': 'ZH',
    '繁體中文': 'TW',
}

ABBR_TO_LANGUAGE = {value: key for key, value in LANGUAGE_TO_ABBR.items()}

# DO-NOT-TRANSLATE text
NO_TRANSLATION = [
    '',
    'OK',
    APPLICATION_NAME,
    *LANGUAGE_TO_ABBR.keys(),
    'TLS',
    XrayCore.name(),
    Hysteria.name(),
    TOR_FAQ_LABEL,
    'socks',
    'http',
]

NO_TRANSLATION_DICT = {key: True for key in NO_TRANSLATION}

TRANSLATION = {
    # Tray Actions
    'Connect': {
        'ES': 'Conectar',
        'ZH': '连接',
        'TW': '連接',
    },
    'Connecting': {
        'ES': 'Conectando',
        'ZH': '正在连接',
        'TW': '正在連接',
    },
    'Connected': {
        'ES': 'Conectado',
        'ZH': '已连接',
        'TW': '已連接',
    },
    'Disconnect': {
        'ES': 'Desconectar',
        'ZH': '断开连接',
        'TW': '斷開連接',
    },
    'Disconnected': {
        'ES': 'Desconectado',
        'ZH': '已断开',
        'TW': '已斷開',
    },
    'Routing': {
        'ES': 'Enrutamiento',
        'ZH': '路由',
        'TW': '路由',
    },
    'Bypass Mainland China': {
        'ES': 'Evitar China Continental',
        'ZH': '绕过中国大陆',
        'TW': '繞過中國大陸',
    },
    'Bypass Iran': {
        'ES': 'Evitar Irán',
        'ZH': '绕过伊朗',
        'TW': '繞過伊朗',
    },
    'Route My Traffic Through Tor': {
        'ES': 'Enrutar Mi Tráfico a Través de Tor',
        'ZH': '通过Tor路由我的流量',
        'TW': '通過Tor路由我的流量',
    },
    'Global': {
        'ES': 'Global',
        'ZH': '全球',
        'TW': '全球',
    },
    'Custom': {
        'ES': 'Personalizado',
        'ZH': '自定义',
        'TW': '自定義',
    },
    'VPN Mode': {
        'ES': 'Modo VPN',
        'ZH': 'VPN模式',
        'TW': 'VPN模式',
    },
    'VPN Mode Disabled (Administrator)': {
        'ES': 'Modo VPN Deshabilitado (Administrador)',
        'ZH': 'VPN模式已禁用（管理员）',
        'TW': 'VPN模式已禁用（管理員）',
    },
    'VPN Mode Disabled (root)': {
        'ES': 'Modo VPN Deshabilitado (root)',
        'ZH': 'VPN模式已禁用（root）',
        'TW': 'VPN模式已禁用（root）',
    },
    'Import': {
        'ES': 'Importar',
        'ZH': '导入',
        'TW': '導入',
    },
    'Import JSON Configuration From Clipboard': {
        'ES': 'Importar Configuración JSON desde el Portapapeles',
        'ZH': '从剪贴板导入JSON配置',
        'TW': '從剪貼板導入JSON配置',
    },
    'Import Share Link From Clipboard': {
        'ES': 'Importar Enlace Compartido desde el Portapapeles',
        'ZH': '从剪贴板导入分享链接',
        'TW': '從剪貼板導入分享鏈接',
    },
    'Edit Configuration...': {
        'ES': 'Editar Configuración...',
        'ZH': '编辑配置...',
        'TW': '編輯配置...',
    },
    'Language': {
        'ES': 'Idioma',
        'ZH': '语言',
        'TW': '語言',
    },
    'Settings': {
        'ES': 'Ajustes',
        'ZH': '设置',
        'TW': '設置',
    },
    'Startup On Boot': {
        'ES': 'Inició en el Arranque',
        'ZH': '开机启动',
        'TW': '開機啓動',
    },
    'Show Progress Bar When Connecting': {
        'ES': 'Mostrar Barra de Progreso al Conectarse',
        'ZH': '连接时显示进度条',
        'TW': '連接時顯示進度條',
    },
    'Show Tab And Spaces In Editor': {
        'ES': 'Mostrar Pestaña y Espacios en el Editor',
        'ZH': '在编辑器中显示制表符和空格',
        'TW': '在編輯器中顯示制表符和空格',
    },
    'Routing Settings...': {
        'ES': 'Ajustes de Enrutamiento...',
        'ZH': '路由设置...',
        'TW': '路由設置...',
    },
    'Tor Relay Settings...': {
        'ES': 'Ajustes de Tor Relay...',
        'ZH': 'Tor Relay设置...',
        'TW': 'Tor Relay設置...',
    },
    'Help': {
        'ES': 'Ayuda',
        'ZH': '帮助',
        'TW': '幫助',
    },
    f'Show {APPLICATION_NAME} Log...': {
        'ES': f'Mostrar Registro de {APPLICATION_NAME}...',
        'ZH': f'显示{APPLICATION_NAME}日志...',
        'TW': f'顯示{APPLICATION_NAME}日志...',
    },
    f'Show {TorRelay.name()} Log...': {
        'ES': f'Mostrar Registro de {TorRelay.name()}...',
        'ZH': f'显示{TorRelay.name()}日志...',
        'TW': f'顯示{TorRelay.name()}日志...',
    },
    'Check For Updates': {
        'ES': 'Comprobar Actualizaciones',
        'ZH': '检查更新',
        'TW': '檢查更新',
    },
    'About': {
        'ES': 'Sobre',
        'ZH': '关于',
        'TW': '關於',
    },
    'Exit': {
        'ES': 'Salida',
        'ZH': '退出',
        'TW': '退出',
    },
    # Server configuration empty
    'Unable to connect': {
        'ES': 'No se puede conectar',
        'ZH': '无法连接',
        'TW': '無法連接',
    },
    'Server configuration empty. Please configure your server first.': {
        'ES': 'Configuración del servidor vacía. Por favor, configure su servidor primero.',
        'ZH': '服务器配置为空。请先配置您的服务器。',
        'TW': '服務器配置爲空。請先配置您的服務器。',
    },
    'Select and double click to activate configuration and connect.': {
        'ES': 'Seleccione y haga doble clic para activar la configuración y conectarse.',
        'ZH': '选中并双击以激活配置并连接。',
        'TW': '選中并雙擊以激活配置并連接。',
    },
    # Http Proxy Configuration Error
    f'{APPLICATION_NAME} cannot find any valid http proxy '
    f'endpoint in your server configuration.': {
        'ES': f'{APPLICATION_NAME} no puede encontrar ningún extremo de '
        f'proxy http válido en la configuración de su servidor.',
        'ZH': f'{APPLICATION_NAME}在您的服务器配置中找不到任何有效的http代理端点。',
        'TW': f'{APPLICATION_NAME}在您的服務器配置中找不到任何有效的http代理端點。',
    },
    # Socks Proxy Configuration Error
    f'{APPLICATION_NAME} cannot find any valid socks proxy '
    f'endpoint in your server configuration.': {
        'ES': f'{APPLICATION_NAME} no puede encontrar ningún extremo de '
        f'proxy socks válido en la configuración de su servidor.',
        'ZH': f'{APPLICATION_NAME}在您的服务器配置中找不到任何有效的socks代理端点。',
        'TW': f'{APPLICATION_NAME}在您的服務器配置中找不到任何有效的socks代理端點。',
    },
    'Please complete your server configuration.': {
        'ES': 'Complete la configuración de su servidor.',
        'ZH': '请完善您的服务器配置。',
        'TW': '請完善您的服務器配置。',
    },
    # Import Share Link From Clipboard MessageBox
    'Invalid share link.': {
        'ES': 'Enlace compartido no válidos.',
        'ZH': '无效的分享链接。',
        'TW': '無效的分享鏈接。',
    },
    'Invalid share link. The content of the clipboard is:': {
        'ES': 'Enlace compartido no válidos. El contenido del portapapeles es:',
        'ZH': '无效的分享链接。剪贴板的内容为：',
        'TW': '無效的分享鏈接。剪貼板的内容為：',
    },
    'Import share link success: ': {
        'ES': 'Importación de enlace compartido exitosa: ',
        'ZH': '导入分享链接成功：',
        'TW': '導入分享鏈接成功：',
    },
    'Imported to row': {
        'ES': 'Importado a la fila',
        'ZH': '导入至行',
        'TW': '導入至行',
    },
    'Import share link success.': {
        'ES': 'Importación de enlace compartido exitosa.',
        'ZH': '导入分享链接成功。',
        'TW': '導入分享鏈接成功。',
    },
    'Go to edit': {
        'ES': 'Ir a editar',
        'ZH': '前往编辑',
        'TW': '前往編輯',
    },
    # Import JSON Configuration From Clipboard MessageBox
    'Invalid JSON data.': {
        'ES': 'Datos JSON no válidos.',
        'ZH': '无效的JSON数据。',
        'TW': '無效的JSON數據。',
    },
    'Invalid JSON data. The content of the clipboard is:': {
        'ES': 'Datos JSON no válidos. El contenido del portapapeles es:',
        'ZH': '无效的JSON数据。剪贴板的内容为：',
        'TW': '無效的JSON數據。剪貼板的内容為：',
    },
    'Import JSON configuration success.': {
        'ES': 'Importación de configuración JSON exitosa.',
        'ZH': '导入JSON配置成功。',
        'TW': '導入JSON配置成功。',
    },
    # Export
    'Export': {
        'ES': 'Exportar',
        'ZH': '导出',
        'TW': '導出',
    },
    'Export Share Link To Clipboard': {
        'ES': 'Exportar Enlace Compartido al Portapapeles',
        'ZH': '导出分享链接至剪贴板',
        'TW': '導出分享鏈接至剪貼板',
    },
    'Export share link to clipboard failed:': {
        'ES': 'Exportar enlace compartido al portapapeles falló:',
        'ZH': '导出分享链接至剪贴板失败：',
        'TW': '導出分享鏈接至剪貼板失敗：',
    },
    'Export share link to clipboard success:': {
        'ES': 'Exportar enlace compartido al portapapeles con éxito:',
        'ZH': '导出分享链接至剪贴板成功：',
        'TW': '導出分享鏈接至剪貼板成功：',
    },
    'Export share link to clipboard partially success:': {
        'ES': 'Exportar enlace compartido al portapapeles parcialmente exitoso:',
        'ZH': '导出分享链接至剪贴板部分成功：',
        'TW': '導出分享鏈接至剪貼板部分成功：',
    },
    'Failed:': {
        'ES': 'Fallido:',
        'ZH': '失败：',
        'TW': '失敗：',
    },
    'Export As QR Code': {
        'ES': 'Exportar Como Código QR',
        'ZH': '导出为二维码',
        'TW': '導出為二維碼',
    },
    'Export as QR code failed:': {
        'ES': 'Exportar como código QR falló:',
        'ZH': '导出为二维码失败：',
        'TW': '導出為二維碼失敗：',
    },
    'Export as QR code success:': {
        'ES': 'Exportar como código QR con éxito:',
        'ZH': '导出为二维码成功：',
        'TW': '導出為二維碼成功：',
    },
    'Export as QR code partially success:': {
        'ES': 'Exportar como código QR parcialmente exitoso:',
        'ZH': '导出为二维码部分成功：',
        'TW': '導出為二維碼部分成功：',
    },
    'Export JSON Configuration To Clipboard': {
        'ES': 'Exportar Configuración JSON al Portapapeles',
        'ZH': '导出JSON配置至剪贴板',
        'TW': '導出JSON配置至剪貼板',
    },
    'Export JSON configuration to clipboard success.': {
        'ES': 'Exportar configuración JSON al portapapeles con éxito.',
        'ZH': '导出JSON配置至剪贴板成功。',
        'TW': '導出JSON配置至剪貼板成功。',
    },
    # Edit Server Configuration Widget
    'Edit Server Configuration': {
        'ES': 'Editar Configuración del Servidor',
        'ZH': '编辑服务器配置',
        'TW': '編輯服務器配置',
    },
    'File': {
        'ES': 'Archivo',
        'ZH': '文件',
        'TW': '文件',
    },
    'New...': {
        'ES': 'Nueva...',
        'ZH': '新建...',
        'TW': '新建...',
    },
    'Untitled': {
        'ES': 'Sin Título',
        'ZH': '未命名',
        'TW': '未命名',
    },
    'Import From File...': {
        'ES': 'Importar desde Archivo...',
        'ZH': '从文件导入...',
        'TW': '從文件導入...',
    },
    'Import File': {
        'ES': 'Importar Archivo',
        'ZH': '导入文件',
        'TW': '導入文件',
    },
    'Save': {
        'ES': 'Guardar',
        'ZH': '保存',
        'TW': '保存',
    },
    'Save As...': {
        'ES': 'Guardar Como...',
        'ZH': '另存为...',
        'TW': '另存爲...',
    },
    'Save File': {
        'ES': 'Guardar Archivo',
        'ZH': '保存文件',
        'TW': '保存文件',
    },
    'Text files (*.json);;All files (*)': {
        'ES': 'Archivos de texto (*.json);;Todos los archivos (*)',
        'ZH': '文本文档 (*.json);;所有文件 (*)',
        'TW': '文本文檔 (*.json);;所有文件 (*)',
    },
    'Text files (*.txt);;All files (*)': {
        'ES': 'Archivos de texto (*.txt);;Todos los archivos (*)',
        'ZH': '文本文档 (*.txt);;所有文件 (*)',
        'TW': '文本文檔 (*.txt);;所有文件 (*)',
    },
    'Error opening file': {
        'ES': 'Error al abrir archivo',
        'ZH': '打开文件时出错',
        'TW': '打開文件時出錯',
    },
    'Error saving configuration': {
        'ES': 'Error al guardar la configuración',
        'ZH': '保存配置时出错',
        'TW': '保存配置時出錯',
    },
    'Error saving file': {
        'ES': 'Error al guardar archivo',
        'ZH': '保存文件时出错',
        'TW': '保存文件時出錯',
    },
    'Error saving log': {
        'ES': 'Error al guardar registro',
        'ZH': '保存日志时出错',
        'TW': '保存日志時出錯',
    },
    'Unable to save log.': {
        'ES': 'No se puede guardar el registro.',
        'ZH': '无法保存日志。',
        'TW': '無法保存日志。',
    },
    'Server configuration corrupted': {
        'ES': 'Configuración del servidor corrupta',
        'ZH': '服务器配置已损坏',
        'TW': '服務器配置已損壞',
    },
    f'{APPLICATION_NAME} cannot restore your server configuration. '
    f'It may have been tampered with.': {
        'ES': f'{APPLICATION_NAME} no puede restaurar la configuración de su servidor. '
        f'Puede que haya sido manipulado.',
        'ZH': f'{APPLICATION_NAME}无法恢复您的服务器配置。它可能已被篡改。',
        'TW': f'{APPLICATION_NAME}無法恢復您的服務器配置。它可能已被篡改。',
    },
    f'The configuration content has been cleared by {APPLICATION_NAME}.': {
        'ES': f'El contenido de la configuración ha sido borrado por {APPLICATION_NAME}.',
        'ZH': f'配置内容已被{APPLICATION_NAME}清空。',
        'TW': f'配置内容已被{APPLICATION_NAME}清空。',
    },
    'Invalid configuration file.': {
        'ES': 'Archivo de configuración inválido.',
        'ZH': '无效的配置文件。',
        'TW': '無效的配置文件。',
    },
    'Hint': {
        'ES': 'Pista',
        'ZH': '提示',
        'TW': '提示',
    },
    f'{APPLICATION_NAME} is currently connected.\n\n'
    f'The new configuration will take effect the next time you connect.': {
        'ES': f'{APPLICATION_NAME} está actualmente conectado.\n\n'
        f'La nueva configuración entrará en vigor la próxima vez que te conectes.',
        'ZH': f'{APPLICATION_NAME}当前已连接。\n\n' f'新配置将在您下次连接时生效。',
        'TW': f'{APPLICATION_NAME}當前已連接。\n\n' f'新配置將在您下次連接時生效。',
    },
    'Reconnect': {
        'ES': 'Reconectar',
        'ZH': '重新连接',
        'TW': '重新連接',
    },
    'Invalid server configuration.': {
        'ES': 'Configuración de servidor no válida.',
        'ZH': '无效的服务器配置。',
        'TW': '無效的服務器配置。',
    },
    'Please check your configuration is in valid JSON format:': {
        'ES': 'Verifique que su configuración esté en formato JSON válido:',
        'ZH': '请检查您的配置是否为有效的JSON格式：',
        'TW': '請檢查您的配置是否為有效的JSON格式：',
    },
    'Save Changes': {
        'ES': 'Guardar Cambios',
        'ZH': '保存更改',
        'TW': '保存更改',
    },
    'The content has been modified. Do you want to save the changes?': {
        'ES': 'El contenido ha sido modificado. ¿Desea guardar los cambios?',
        'ZH': '内容已修改。您要保存更改吗？',
        'TW': '内容已修改。您要保存更改嗎？',
    },
    'Discard': {
        'ES': 'Descartar',
        'ZH': '不保存',
        'TW': '不保存',
    },
    'Cancel': {
        'ES': 'Cancelar',
        'ZH': '取消',
        'TW': '取消',
    },
    'Delete': {
        'ES': 'Eliminar',
        'ZH': '删除',
        'TW': '刪除',
    },
    'Delete these configuration?': {
        'ES': '¿Eliminar esta configuración?',
        'ZH': '删除这些配置？',
        'TW': '刪除這些配置？',
    },
    'Delete this configuration?': {
        'ES': '¿Eliminar esta configuración?',
        'ZH': '删除此配置？',
        'TW': '刪除此配置？',
    },
    'Connecting. Please wait.': {
        'ES': 'Conectando. Espere por favor.',
        'ZH': '正在连接，请稍候。',
        'TW': '正在連接，請稍候。',
    },
    'Please save any changes to continue.': {
        'ES': 'Guarde los cambios para continuar.',
        'ZH': '请保存所有更改以继续。',
        'TW': '請保存所有更改以繼續',
    },
    'Edit': {
        'ES': 'Editar',
        'ZH': '编辑',
        'TW': '編輯',
    },
    'Undo': {
        'ES': 'Deshacer',
        'ZH': '撤销',
        'TW': '撤銷',
    },
    'Redo': {
        'ES': 'Rehacer',
        'ZH': '重做',
        'TW': '重做',
    },
    'Cut': {
        'ES': 'Cortar',
        'ZH': '剪切',
        'TW': '剪切',
    },
    'Copy': {
        'ES': 'Copiar',
        'ZH': '拷贝',
        'TW': '拷貝',
    },
    'Paste': {
        'ES': 'Pegar',
        'ZH': '粘贴',
        'TW': '粘貼',
    },
    'Select All': {
        'ES': 'Seleccionar Todo',
        'ZH': '全选',
        'TW': '全選',
    },
    'Set Indent': {
        'ES': 'Establecer sangría',
        'ZH': '设置缩进',
        'TW': '設置縮進',
    },
    'Indent...': {
        'ES': 'Sangría...',
        'ZH': '缩进...',
        'TW': '縮進...',
    },
    'Indent:': {
        'ES': 'Sangría:',
        'ZH': '缩进：',
        'TW': '縮進：',
    },
    'Error setting indent': {
        'ES': 'Error al establecer sangría',
        'ZH': '设置缩进时出错',
        'TW': '設置縮進時出錯',
    },
    'View': {
        'ES': 'Vista',
        'ZH': '显示',
        'TW': '顯示',
    },
    'Zoom In': {
        'ES': 'Acercar',
        'ZH': '变大',
        'TW': '變大',
    },
    'Zoom Out': {
        'ES': 'Alejar',
        'ZH': '变小',
        'TW': '變小',
    },
    'Remark': {
        'ES': 'Observación',
        'ZH': '别名',
        'TW': '別名',
    },
    'Protocol': {
        'ES': 'Protocolo',
        'ZH': '协议',
        'TW': '協議',
    },
    'Address': {
        'ES': 'Dirección',
        'ZH': '地址',
        'TW': '地址',
    },
    'Port': {
        'ES': 'Puerto',
        'ZH': '端口',
        'TW': '端口',
    },
    'Transport': {
        'ES': 'Transporte',
        'ZH': '传输方式',
        'TW': '傳輸方式',
    },
    'Server': {
        'ES': 'Servidor',
        'ZH': '服务器',
        'TW': '服務器',
    },
    # Server Widget buttons
    'Move Up': {
        'ES': 'Ascender',
        'ZH': '上移',
        'TW': '上移',
    },
    'Move Down': {
        'ES': 'Mover Hacia Abajo',
        'ZH': '下移',
        'TW': '下移',
    },
    'Duplicate': {
        'ES': 'Duplicado',
        'ZH': '克隆',
        'TW': '克隆',
    },
    'Scroll To Activated Server': {
        'ES': 'Desplácese Hasta el Servidor Activado',
        'ZH': '滚动到激活的服务器',
        'TW': '滾動到激活的服務器',
    },
    # Edit Routing widget
    'Edit Routing': {
        'ES': 'Editar Enrutamiento',
        'ZH': '编辑路由',
        'TW': '編輯路由',
    },
    'Type': {
        'ES': 'Tipo',
        'ZH': '类型',
        'TW': '類型',
    },
    'Built-in': {
        'ES': 'Incorporado',
        'ZH': '内置',
        'TW': '内置',
    },
    'Routing Rules': {
        'ES': 'Reglas de Enrutamiento',
        'ZH': '路由规则',
        'TW': '路由規則',
    },
    'User Defined': {
        'ES': 'Usuario Definido',
        'ZH': '用户定义',
        'TW': '用戶定義',
    },
    'Add routing': {
        'ES': 'Agregar enrutamiento',
        'ZH': '添加路由',
        'TW': '添加路由',
    },
    'Enter routing remark:': {
        'ES': 'Introducir comentario de enrutamiento:',
        'ZH': '输入路由名称：',
        'TW': '輸入路由名稱：',
    },
    'Add': {
        'ES': 'Agregar',
        'ZH': '添加',
        'TW': '添加',
    },
    'Import Asset File...': {
        'ES': 'Importar Archivo de Activos...',
        'ZH': '导入资源文件...',
        'TW': '導入資源文件...',
    },
    'Error saving routing configuration': {
        'ES': 'Error al guardar la configuración de enrutamiento',
        'ZH': '保存路由配置时出错',
        'TW': '保存路由配置時出錯',
    },
    **dict(
        list(
            [
                f'Edit {coreName} Routing Rules',
                {
                    'ES': f'Editar Reglas de Enrutamiento de {coreName}',
                    'ZH': f'编辑{coreName}路由规则',
                    'TW': f'編輯{coreName}路由規則',
                },
            ]
        )
        for coreName in [XrayCore.name(), Hysteria.name()]
    ),
    f'{XrayCore.name()} Routing Rules': {
        'ES': f'Reglas de Enrutamiento de {XrayCore.name()}',
        'ZH': f'{XrayCore.name()}路由规则',
        'TW': f'{XrayCore.name()}路由規則',
    },
    f'Note: If acl is empty or does not exist, {APPLICATION_NAME} '
    f'will fall back to proxy all traffic.': {
        'ES': f'NOTA: Si la ACL está vacía o no existe, '
        f'{APPLICATION_NAME} volverá a utilizar proxy para todo el tráfico.',
        'ZH': f'注意：如果acl为空或不存在，{APPLICATION_NAME}将回落到代理所有流量。',
        'TW': f'注意：如果acl為空或不存在，{APPLICATION_NAME}將回落到代理所有流量。',
    },
    f'Note: "Custom" will use acl and mmdb defined in current user configuration.': {
        'ES': f'NOTA: "Personalizado" utilizará la acl y mmdb definidas en la configuración de usuario actual',
        'ZH': f'注意："自定义"将使用当前用户配置中定义的acl和mmdb。',
        'TW': f'注意："自定義"將使用當前用戶配置中定義的acl和mmdb。',
    },
    # Asset Viewer
    'Asset File': {
        'ES': 'Activos',
        'ZH': '资源文件',
        'TW': '資源文件',
    },
    'Asset file already exists. Overwrite?': {
        'ES': 'Archivo de activos ya existe. ¿Sobrescribir?',
        'ZH': '资源文件已存在。是否覆盖？',
        'TW': '資源文件已存在。是否覆蓋？',
    },
    'Error import asset file.': {
        'ES': 'Error al importar el archivo de activos.',
        'ZH': '导入资源文件出错。',
        'TW': '導入資源文件出錯。',
    },
    'Import asset file success.': {
        'ES': 'Importar archivo de activos con éxito.',
        'ZH': '导入资源文件成功。',
        'TW': '導入資源文件成功。',
    },
    'Delete these asset files?': {
        'ES': '¿Eliminar estos archivos de activos?',
        'ZH': '删除这些资源文件？',
        'TW': '刪除這些資源文件？',
    },
    'Delete this asset file?': {
        'ES': '¿Eliminar este archivo de activos?',
        'ZH': '删除该资源文件？',
        'TW': '刪除該資源文件？',
    },
    'All files (*)': {
        'ES': 'Todos los archivos (*)',
        'ZH': '所有文件 (*)',
        'TW': '所有文件 (*)',
    },
    # Log Viewer
    'Log Viewer': {
        'ES': 'Visor de Registro',
        'ZH': '日志查看器',
        'TW': '日志查看器',
    },
    # Tor Relay Settings
    'Tor Relay Settings': {
        'ES': 'Ajustes de Tor Relay',
        'ZH': 'Tor Relay设置',
        'TW': 'Tor Relay設置',
    },
    'Tunnel Port': {
        'ES': 'Puerto de Túnel',
        'ZH': '隧道端口',
        'TW': '隧道端口',
    },
    'Proxy': {
        'ES': 'Proxy',
        'ZH': '代理',
        'TW': '代理',
    },
    'Other': {
        'ES': 'Otro',
        'ZH': '其它',
        'TW': '其它',
    },
    'Use Proxy': {
        'ES': 'Usa Proxy',
        'ZH': '使用代理',
        'TW': '使用代理',
    },
    'Log Level': {
        'ES': 'Nivel de Registro',
        'ZH': '日志级别',
        'TW': '日志級別',
    },
    'Relay Establish Timeout (seconds)': {
        'ES': 'Establecer Tiempo de Espera de Relay (segundos)',
        'ZH': 'Relay建立超时（秒）',
        'TW': 'Relay建立超時（秒）',
    },
    # Check For Updates
    'Check for updates failed.': {
        'ES': 'Error al comprobar actualizaciones.',
        'ZH': '检查更新失败。',
        'TW': '檢查更新失敗。',
    },
    'New version available: ': {
        'ES': 'Nueva versión disponible: ',
        'ZH': '新版本可用：',
        'TW': '新版本可用：',
    },
    'Go to download page?': {
        'ES': '¿Ir a la página de descarga?',
        'ZH': '是否前往下载页面？',
        'TW': '是否前往下載頁面？',
    },
    f'{APPLICATION_NAME} is already the latest version.': {
        'ES': f'{APPLICATION_NAME} ya es la última versión.',
        'ZH': f'{APPLICATION_NAME}已是最新版本。',
        'TW': f'{APPLICATION_NAME}已是最新版本。',
    },
    f'Thank you for using {APPLICATION_NAME}.': {
        'ES': f'Gracias por usar {APPLICATION_NAME}.',
        'ZH': f'感谢您使用{APPLICATION_NAME}。',
        'TW': f'感謝您使用{APPLICATION_NAME}。',
    },
    # Tray
    'Unconfigured server': {
        'ES': 'Servidor no configurado',
        'ZH': '未配置的服务器',
        'TW': '未配置的服務器',
    },
    'Already started': {
        'ES': 'Ya ha comenzado',
        'ZH': '已启动',
        'TW': '已啓動',
    },
    'Invalid server configuration': {
        'ES': 'Configuración de servidor no válida',
        'ZH': '无效的服务器配置',
        'TW': '無效的服務器配置',
    },
    'Failed to start core': {
        'ES': 'No se pudo iniciar el núcleo',
        'ZH': '内核启动失败',
        'TW': '内核啓動失敗',
    },
    'Connection test failed': {
        'ES': 'Falló la prueba de conexión',
        'ZH': '连接测试失败',
        'TW': '連接測試失敗',
    },
    'Connection to server has been lost': {
        'ES': 'Se perdió la conexión con el servidor',
        'ZH': '与服务器的连接丢失',
        'TW': '與服務器的連接丟失',
    },
    'Core terminated unexpectedly': {
        'ES': 'Núcleo terminado inesperadamente',
        'ZH': '内核意外终止',
        'TW': '内核意外終止',
    },
    'Routing changed: ': {
        'ES': 'Ruta cambiada: ',
        'ZH': '路由已更改：',
        'TW': '路由已更改：',
    },
    f'{TorRelay.name()} establish timeout': {
        'ES': f'Establecer tiempo de espera de {TorRelay.name()}',
        'ZH': f'{TorRelay.name()}建立超时',
        'TW': f'{TorRelay.name()}建立超時',
    },
    'Cannot find Tor CLI in PATH': {
        'ES': 'No se puede encontrar Tor CLI en PATH',
        'ZH': '在PATH中找不到Tor CLI',
        'TW': '在PATH中找不到Tor CLI',
    },
    # Errors
    f'{APPLICATION_NAME} is not be able to run on this operating system.': {
        'ES': f'{APPLICATION_NAME} no puede ejecutarse en este sistema operativo.',
        'ZH': f'{APPLICATION_NAME}无法在此操作系统上运行。',
        'TW': f'{APPLICATION_NAME}無法在此操作系統上運行。',
    },
    'Operating system information:': {
        'ES': 'Información del sistema operativo:',
        'ZH': '操作系统信息：',
        'TW': '操作系統信息：',
    },
    f'{APPLICATION_NAME} stopped unexpectedly due to an unknown exception.': {
        'ES': f'{APPLICATION_NAME} se detuvo inesperadamente debido a una excepción desconocida.',
        'ZH': f'由于一个未知异常，{APPLICATION_NAME}意外终止。',
        'TW': f'由於一個未知異常，{APPLICATION_NAME}意外終止。',
    },
    f'{APPLICATION_NAME} encountered an internal error and needs to be stopped.': {
        'ES': f'{APPLICATION_NAME} encontró un error interno y debe detenerse',
        'ZH': f'{APPLICATION_NAME}遇到内部错误，需要終止。',
        'TW': f'{APPLICATION_NAME}遇到内部錯誤，需要終止。',
    },
    'Crash log has been saved to: ': {
        'ES': 'El registro de errores se ha guardado en: ',
        'ZH': '崩溃日志已保存到：',
        'TW': '崩潰日志已保存到：',
    },
    'Open crash log': {
        'ES': 'Abrir registro de fallas',
        'ZH': '打开崩溃日志',
        'TW': '打開崩潰日志',
    },
}

installTranslation(TRANSLATION)
