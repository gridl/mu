# -*- coding: utf-8 -*-
"""
Tests for the Editor and REPL logic.
"""
import os.path
import json
import pytest
import mu.editor
from PyQt5.QtWidgets import QMessageBox
from unittest import mock


SESSION = json.dumps({
    'theme': 'night',
    'paths': [
        'path/foo.py',
        'path/bar.py',
    ],
})


def test_CONSTANTS():
    """
    Ensure the expected constants exist.
    """
    assert mu.editor.HOME_DIRECTORY
    assert mu.editor.MICROPYTHON_DIRECTORY
    assert mu.editor.DATA_DIR
    assert mu.editor.SETTINGS_FILE


def test_REPL_posix():
    """
    The port is set correctly in a posix environment.
    """
    with mock.patch('os.name', 'posix'):
        r = mu.editor.REPL('ttyACM0')
        assert r.port == '/dev/ttyACM0'


def test_REPL_nt():
    """
    The port is set correctly in an nt (Windows) environment.
    """
    with mock.patch('os.name', 'nt'):
        r = mu.editor.REPL('COM0')
        assert r.port == 'COM0'


def test_REPL_unsupported():
    """
    A NotImplementedError is raised on an unsupported OS.
    """
    with mock.patch('os.name', 'SPARC'):
        with pytest.raises(NotImplementedError):
            mu.editor.REPL('tty0')


def test_editor_init():
    """
    Ensure a new instance is set-up correctly.
    """
    view = mock.MagicMock()
    # Check the editor attempts to create required directories if they don't
    # already exist.
    with mock.patch('os.path.exists', return_value=False), \
            mock.patch('os.makedirs', return_value=None) as mkd:
        e = mu.editor.Editor(view)
        assert e._view == view
        assert e.repl is None
        assert e.theme == 'day'
        assert mkd.call_count == 2
        assert mkd.call_args_list[0][0][0] == mu.editor.MICROPYTHON_DIRECTORY
        assert mkd.call_args_list[1][0][0] == mu.editor.DATA_DIR


def test_editor_restore_session():
    """
    A correctly specified session is restored properly.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.read.return_value = SESSION
    with mock.patch('builtins.open', mock_open), \
            mock.patch('os.path.exists', return_value=True):
        ed.restore_session()
    assert ed.theme == 'night'
    assert mock_open.return_value.read.call_count == 3
    assert ed._view.add_tab.call_count == 2
    view.set_theme.assert_called_once_with('night')


def test_editor_restore_session_missing_files():
    """
    Missing files that were opened tabs in the previous session are safely
    ignored when attempting to restore them.
    """
    view = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    fake_settings = os.path.join(os.path.dirname(__file__), 'settings.json')
    with mock.patch('os.path.exists', return_value=True), \
            mock.patch('mu.editor.SETTINGS_FILE', fake_settings):
        ed.restore_session()
    assert ed._view.add_tab.call_count == 0


def test_editor_restore_session_no_session_file():
    """
    If there's no prior session file (such as upon first start) then simply
    start up the editor with an empty untitled tab.
    """
    view = mock.MagicMock()
    view.tab_count = 0
    ed = mu.editor.Editor(view)
    ed._view.add_tab = mock.MagicMock()
    with mock.patch('os.path.exists', return_value=False):
        ed.restore_session()
    py = 'from microbit import *\n\n# Write your code here :-)'
    ed._view.add_tab.assert_called_once_with(None, py)


def test_flash_no_tab():
    """
    If there are no active tabs simply return.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.editor.Editor(view)
    assert ed.flash() is None


def test_flash_with_attached_device():
    """
    Ensure the expected calls are made to uFlash and a helpful status message
    is enacted.
    """
    with mock.patch('mu.editor.uflash.hexlify', return_value=''), \
            mock.patch('mu.editor.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.editor.uflash.find_microbit', return_value='bar'),\
            mock.patch('mu.editor.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.editor.Editor(view)
        ed.flash()
        assert view.show_message.call_count == 1
        hex_file_path = os.path.join('bar', 'micropython.hex')
        s.assert_called_once_with('foo', hex_file_path)


def test_flash_without_device():
    """
    If no device is found then ensure a helpful status messgae is enacted.
    """
    with mock.patch('mu.editor.uflash.hexlify', return_value=''), \
            mock.patch('mu.editor.uflash.embed_hex', return_value='foo'), \
            mock.patch('mu.editor.uflash.find_microbit', return_value=''), \
            mock.patch('mu.editor.uflash.save_hex', return_value=None) as s:
        view = mock.MagicMock()
        view.current_tab.text = mock.MagicMock(return_value='')
        view.show_message = mock.MagicMock()
        ed = mu.editor.Editor(view)
        ed.flash()
        message = 'Could not find an attached BBC micro:bit.'
        view.show_message.assert_called_once_with(message)
        assert s.call_count == 0


def test_add_repl_already_exists():
    """
    Ensure the editor raises a RuntimeError if the repl already exists.
    """
    view = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.repl = True
    with pytest.raises(RuntimeError):
        ed.add_repl()


def test_add_repl_no_port():
    """
    If it's not possible to find a connected micro:bit then ensure a helpful
    message is enacted.
    """
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    ed = mu.editor.Editor(view)
    with mock.patch('mu.editor.find_microbit', return_value=False):
        ed.add_repl()
    assert view.show_message.call_count == 1
    message = 'Could not find an attached BBC micro:bit.'
    assert view.show_message.call_args[0][0] == message


def test_add_repl_ioerror():
    """
    Sometimes when attempting to connect to the device there is an IOError
    because it's still booting up or connecting to the host computer. In this
    case, ensure a useful message is displayed.
    """
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    ex = IOError('BOOM')
    view.add_repl = mock.MagicMock(side_effect=ex)
    ed = mu.editor.Editor(view)
    with mock.patch('mu.editor.find_microbit', return_value='COM0'):
        ed.add_repl()
    assert view.show_message.call_count == 1
    assert view.show_message.call_args[0][0] == str(ex)


def test_add_repl():
    """
    Nothing goes wrong so check the _view.add_repl gets the expected argument.
    """
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    view.add_repl = mock.MagicMock()
    ed = mu.editor.Editor(view)
    with mock.patch('mu.editor.find_microbit', return_value='COM0'), \
            mock.patch('os.name', 'nt'):
        ed.add_repl()
    assert view.show_message.call_count == 0
    assert view.add_repl.call_args[0][0].port == 'COM0'


def test_remove_repl_is_none():
    """
    If there's no repl to remove raise a RuntimeError.
    """
    view = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.repl = None
    with pytest.raises(RuntimeError):
        ed.remove_repl()


def test_remove_repl():
    """
    If there is a repl, make sure it's removed as expected and the state is
    updated.
    """
    view = mock.MagicMock()
    view.remove_repl = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.repl = True
    ed.remove_repl()
    assert view.remove_repl.call_count == 1
    assert ed.repl is None


def test_toggle_repl_on():
    """
    There is no repl, so toggle on.
    """
    view = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.add_repl = mock.MagicMock()
    ed.repl = None
    ed.toggle_repl()
    assert ed.add_repl.call_count == 1


def test_toggle_repl_off():
    """
    There is a repl, so toggle off.
    """
    view = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.remove_repl = mock.MagicMock()
    ed.repl = True
    ed.toggle_repl()
    assert ed.remove_repl.call_count == 1


def test_toggle_theme_to_night():
    """
    The current theme is 'day' so toggle to night. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.theme = 'day'
    ed.toggle_theme()
    assert ed.theme == 'night'
    view.set_theme.assert_called_once_with(ed.theme)


def test_toggle_theme_to_day():
    """
    The current theme is 'day' so toggle to night. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.theme = 'night'
    ed.toggle_theme()
    assert ed.theme == 'day'
    view.set_theme.assert_called_once_with(ed.theme)


def test_new():
    """
    Ensure an untitled tab is added to the UI.
    """
    view = mock.MagicMock()
    view.add_tab = mock.MagicMock()
    ed = mu.editor.Editor(view)
    ed.new()
    view.add_tab.assert_called_once_with(None, '')


def test_load_python_file():
    """
    If the user specifies a Python file (*.py) then ensure it's loaded and
    added as a tab.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value='foo.py')
    view.add_tab = mock.MagicMock()
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.read.return_value = 'PYTHON'
    with mock.patch('builtins.open', mock_open):
        ed.load()
    assert view.get_load_path.call_count == 1
    view.add_tab.assert_called_once_with('foo.py', 'PYTHON')


def test_load_hex_file():
    """
    If the user specifies a hex file (*.hex) then ensure it's loaded and
    added as a tab.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value='foo.hex')
    view.add_tab = mock.MagicMock()
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.read.return_value = 'PYTHON'
    hex_file = 'RECOVERED'
    with mock.patch('builtins.open', mock_open), \
            mock.patch('mu.editor.uflash.extract_script',
                       return_value=hex_file) as s:
        ed.load()
    assert view.get_load_path.call_count == 1
    assert s.call_count == 1
    view.add_tab.assert_called_once_with(None, 'RECOVERED')


def test_load_error():
    """
    Ensure that anything else is just ignored.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value='foo.py')
    view.add_tab = mock.MagicMock()
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock(side_effect=FileNotFoundError())
    with mock.patch('builtins.open', mock_open):
        ed.load()
    assert view.get_load_path.call_count == 1
    assert view.add_tab.call_count == 0


def test_save_no_tab():
    """
    If there's no active tab then do nothing.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.editor.Editor(view)
    ed.save()
    # If the code fell through then the tab state would be modified.
    assert view.current_tab is None


def test_save_no_path():
    """
    If there's no path associated with the tab then request the user provide
    one.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = None
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.get_save_path = mock.MagicMock(return_value='foo.py')
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    ed = mu.editor.Editor(view)
    with mock.patch('builtins.open', mock_open):
        ed.save()
    assert view.current_tab.modified is False
    mock_open.assert_called_once_with('foo.py', 'w')
    mock_open.return_value.write.assert_called_once_with('foo')
    view.get_save_path.assert_called_once_with(mu.editor.MICROPYTHON_DIRECTORY)


def test_save_no_path_no_path_give():
    """
    If there's no path associated with the tab and the user cancels providing
    one ensure the path is correctly re-set.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = None
    view.get_save_path = mock.MagicMock(return_value='')
    ed = mu.editor.Editor(view)
    ed.save()
    # The path isn't the empty string returned from get_save_path.
    assert view.current_tab.path is None


def test_save_python_file():
    """
    If the path is a Python file (ending in *.py) then save it and reset the
    modified flag.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = 'foo.py'
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.get_save_path = mock.MagicMock()
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    ed = mu.editor.Editor(view)
    with mock.patch('builtins.open', mock_open):
        ed.save()
    assert view.current_tab.modified is False
    mock_open.assert_called_once_with('foo.py', 'w')
    mock_open.return_value.write.assert_called_once_with('foo')
    assert view.get_save_path.call_count == 0


def test_save_with_no_file_extension():
    """
    If the path doesn't end in *.py then append it to the filename.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = 'foo'
    view.current_tab.text = mock.MagicMock(return_value='foo')
    view.get_save_path = mock.MagicMock()
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    ed = mu.editor.Editor(view)
    with mock.patch('builtins.open', mock_open):
        ed.save()
    assert view.current_tab.modified is False
    mock_open.assert_called_once_with('foo.py', 'w')
    mock_open.return_value.write.assert_called_once_with('foo')
    assert view.get_save_path.call_count == 0


def test_zoom_in():
    """
    Ensure the UI layer is zoomed in.
    """
    view = mock.MagicMock()
    view.zoom_in = mock.MagicMock(return_value=None)
    ed = mu.editor.Editor(view)
    ed.zoom_in()
    assert view.zoom_in.call_count == 1


def test_zoom_out():
    """
    Ensure the UI layer is zoomed out.
    """
    view = mock.MagicMock()
    view.zoom_out = mock.MagicMock(return_value=None)
    ed = mu.editor.Editor(view)
    ed.zoom_out()
    assert view.zoom_out.call_count == 1


def test_quit_modified_cancelled_from_button():
    """
    If the user quits and there's unsaved work, and they cancel the "quit" then
    do nothing.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit()
    assert view.show_confirmation.call_count == 1
    assert mock_open.call_count == 0


def test_quit_modified_cancelled_from_event():
    """
    If the user quits and there's unsaved work, and they cancel the "quit" then
    do nothing.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 1
    assert mock_open.call_count == 0


def test_quit_modified_ok():
    """
    If the user quits and there's unsaved work that's ignored then proceed to
    save the session.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mock_open.call_count == 1
    assert mock_open.return_value.write.call_count > 0


def test_quit_save_tabs_with_paths():
    """
    When saving the session, ensure those tabs with associated paths are
    logged in the session file.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = 'foo.py'
    view.widgets = [w1, ]
    ed = mu.editor.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mock_open.call_count == 1
    assert mock_open.return_value.write.call_count > 0
    recovered = ''.join([i[0][0] for i
                        in mock_open.return_value.write.call_args_list])
    session = json.loads(recovered)
    assert 'foo.py' in session['paths']


def test_quit_save_theme():
    """
    When saving the session, ensure the theme is logged in the session file.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = 'foo.py'
    view.widgets = [w1, ]
    ed = mu.editor.Editor(view)
    ed.theme = 'night'
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None), \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mock_open.call_count == 1
    assert mock_open.return_value.write.call_count > 0
    recovered = ''.join([i[0][0] for i
                        in mock_open.return_value.write.call_args_list])
    session = json.loads(recovered)
    assert session['theme'] == 'night'


def test_quit_calls_sys_exit():
    """
    Ensure that sys.exit(0) is called.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = 'foo.py'
    view.widgets = [w1, ]
    ed = mu.editor.Editor(view)
    ed.theme = 'night'
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with mock.patch('sys.exit', return_value=None) as ex, \
            mock.patch('builtins.open', mock_open):
        ed.quit(mock_event)
    ex.assert_called_once_with(0)
