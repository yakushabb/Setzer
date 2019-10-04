#!/usr/bin/env python3
# coding: utf-8

# Copyright (C) 2018 Robert Griesel
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib

import sys, time

import model.model_workspace as model_workspace
import viewgtk.viewgtk as view
import controller.controller_settings as settingscontroller
import controller.controller_workspace as workspacecontroller
import controller.controller_shortcuts as shortcutscontroller
import helpers.helpers as helpers
import dialogs.preferences.preferences as preferences_dialog


class MainApplicationController(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self)

    def do_activate(self):
        ''' Everything starts here. '''
        
        # load settings
        self.settings = settingscontroller.Settings()
        
        # setup dark mode
        dm_default = GLib.Variant.new_boolean(self.settings.get_value('preferences', 'prefer_dark_mode'))
        self.settings.gtksettings.get_default().set_property('gtk-application-prefer-dark-theme', dm_default)
        self.toggle_dark_mode_action = Gio.SimpleAction.new_stateful('toggle-dark-mode', None, dm_default)
        self.toggle_dark_mode_action.connect('activate', self.toggle_dark_mode)
        self.add_action(self.toggle_dark_mode_action)
        
        # init model
        self.workspace = model_workspace.Workspace()
        
        # init view
        self.construct_application_menu()

        self.main_window = view.MainWindow(self)
        self.main_window.set_default_size(self.settings.get_value('window_state', 'width'), 
                                          self.settings.get_value('window_state', 'height'))
        self.main_window.current_width = self.settings.get_value('window_state', 'width')
        self.main_window.current_height = self.settings.get_value('window_state', 'height')
        self.fg_color = helpers.theme_color_to_rgba(self.main_window.get_style_context(), 'theme_fg_color')
        self.bg_color = helpers.theme_color_to_rgba(self.main_window.get_style_context(), 'theme_bg_color')
        self.style_context = self.main_window.get_style_context()

        self.first_window_state_event = True
        if self.settings.get_value('window_state', 'is_maximized'):
            self.main_window.maximize()
        else: 
            self.main_window.unmaximize()

        self.main_window.show_all()
        self.observe_main_window()

        # init dialogs
        self.preferences_dialog = preferences_dialog.PreferencesDialog(self.main_window, self.settings)

        # init controller
        self.workspace_controller = workspacecontroller.WorkspaceController(self.workspace, self.main_window, self.settings, self)
        self.setup_hamburger_menu()
        self.shortcuts_controller = shortcutscontroller.ShortcutsController(self.workspace, self.workspace_controller, self.main_window, self)

    def do_startup(self):
        Gtk.Application.do_startup(self)

    '''
    *** main observer functions
    '''

    def observe_main_window(self):
        self.main_window.connect('size-allocate', self.on_window_size_allocate)
        self.main_window.connect('notify::is-maximized', self.on_window_maximize_event)
        self.main_window.connect('delete-event', self.on_window_close)
        self.main_window.connect('draw', self.on_window_draw)
    
    '''
    *** signal handlers: main window
    '''
    
    def on_window_size_allocate(self, main_window, window_size):
        ''' signal handler, update window size variables '''

        if not main_window.ismaximized:
            main_window.current_width, main_window.current_height = main_window.get_size()

    def on_window_maximize_event(self, main_window, state_event):
        ''' signal handler, update window state variables '''

        main_window.ismaximized = main_window.is_maximized()
        return False
    
    def on_window_draw(self, main_window, context):
        ''' check for theme changes, update sidebar, textviews '''

        fg_color = helpers.theme_color_to_rgba(self.style_context, 'theme_fg_color')
        bg_color = helpers.theme_color_to_rgba(self.style_context, 'theme_bg_color')
        if self.fg_color.red != fg_color.red or self.bg_color.red != bg_color.red:
            self.fg_color = fg_color
            self.bg_color = bg_color
            
            try: document_controllers = self.workspace_controller.document_controllers
            except AttributeError: pass
            else:
                is_dark_mode = helpers.is_dark_mode(main_window)
                for document in self.workspace_controller.document_controllers:
                    if is_dark_mode:
                        document.set_use_dark_scheme(True)
                    else:
                        document.set_use_dark_scheme(False)
                
                parent_folder = 'dark' if is_dark_mode else 'light'
                for page_view in self.workspace_controller.sidebar_controller.page_views:
                    page_view.change_parent_folder(parent_folder)
                sidebar = main_window.sidebar
        return False

    def save_window_state(self):
        ''' save window state variables '''

        main_window = self.main_window
        self.settings.set_value('window_state', 'width', main_window.current_width)
        self.settings.set_value('window_state', 'height', main_window.current_height)
        self.settings.set_value('window_state', 'is_maximized', main_window.ismaximized)

        sidebar_visible = self.main_window.shortcuts_bar.sidebar_toggle.get_active()
        self.settings.set_value('window_state', 'show_sidebar', sidebar_visible)
        if main_window.sidebar_visible:
            sidebar_position = main_window.sidebar_paned.get_position()
        elif self.workspace_controller.sidebar_controller.sidebar_position > 0:
            sidebar_position = self.workspace_controller.sidebar_controller.sidebar_position
        else:
            sidebar_position = -1
        self.settings.set_value('window_state', 'sidebar_paned_position', sidebar_position)

        preview_visible = self.main_window.headerbar.preview_toggle.get_active()
        self.settings.set_value('window_state', 'show_preview', preview_visible)
        if main_window.preview_visible:
            preview_position = main_window.preview_paned.get_position()
        elif self.workspace_controller.preview_controller.preview_position > 0:
            preview_position = self.workspace_controller.preview_controller.preview_position
        else:
            preview_position = -1
        self.settings.set_value('window_state', 'preview_paned_position', preview_position)
        self.settings.pickle()
        
    def on_window_close(self, main_window, event=None):
        ''' signal handler, ask user to save unsaved documents or discard changes '''

        return_to_active_document = False
        
        for document in self.workspace.open_documents: document.save_document_data()

        documents = self.workspace.get_unsaved_documents()
        if documents == None: 
            self.workspace.save_to_disk()
            self.save_window_state()
            return False

        active_document = self.workspace.get_active_document()
        if active_document == None:
            return False

        self.save_changes_dialog = view.dialogs.CloseConfirmation(self.main_window, documents)
        response = self.save_changes_dialog.run()
        documents_still_to_save = list()
        if response == Gtk.ResponseType.NO:
            self.save_changes_dialog.hide()
            self.workspace.save_to_disk()
            self.save_window_state()
            return False
        elif response == Gtk.ResponseType.YES:
            selected_documents = list()
            if len(documents) == 1:
                selected_documents.append(documents[0])
            else:
                for child in self.save_changes_dialog.chooser.get_children():
                    if child.get_child().get_active():
                        number = int(child.get_child().get_name()[29:])
                        selected_documents.append(documents[number])
            for document in selected_documents:
                if document.get_filename() == None:
                    self.workspace.set_active_document(document)
                    return_to_active_document = True
                    dialog = view.dialogs.SaveDocument(self.main_window)
                    dialog.set_current_name('.tex')
                    response = dialog.run()
                    if response == Gtk.ResponseType.OK:
                        filename = dialog.get_filename()
                        document.set_filename(filename)
                        document.save_to_disk()
                        self.workspace.update_recently_opened_document(filename)
                    else:
                        documents_still_to_save.append(document)
                    dialog.hide()
                else:
                    document.save_to_disk()
            if return_to_active_document == True:
                self.workspace.set_active_document(document)

            self.save_changes_dialog.hide()
            self.workspace.save_to_disk()
            self.save_window_state()
            if len(documents_still_to_save) >= 1:
                self.workspace.set_active_document(documents_still_to_save[-1])
                return True
            else:
                return False
        else:
            self.save_changes_dialog.hide()
            return True

    '''
    *** app menu
    '''

    def construct_application_menu(self):
        show_preferences_dialog_action = Gio.SimpleAction.new('show-preferences-dialog', None)
        show_preferences_dialog_action.connect('activate', self.on_appmenu_show_preferences_dialog)
        self.add_action(show_preferences_dialog_action)

        show_about_dialog_action = Gio.SimpleAction.new('show-about-dialog', None)
        show_about_dialog_action.connect('activate', self.on_appmenu_show_about_dialog)
        self.add_action(show_about_dialog_action)

        quit_action = Gio.SimpleAction.new('quit', None)
        quit_action.connect('activate', self.on_appmenu_quit)
        self.add_action(quit_action)
        
    def on_appmenu_show_preferences_dialog(self, action=None, parameter=''):
        self.preferences_dialog.run()

    def on_appmenu_show_about_dialog(self, action, parameter=''):
        ''' show popup with some information about the app. '''
        
        self.about_dialog = Gtk.AboutDialog()
        self.about_dialog.set_transient_for(self.main_window)
        self.about_dialog.set_modal(True)
        self.about_dialog.set_program_name('Setzer')
        self.about_dialog.set_version('0.0.1')
        self.about_dialog.set_copyright('Copyright © 2018-2019 - the Setzer developers')
        self.about_dialog.set_comments('Setzer is a LaTeX editor.')
        self.about_dialog.set_license_type(Gtk.License.GPL_3_0)
        self.about_dialog.set_website('https://github.com/cvfosammmm/setzer')
        self.about_dialog.set_website_label('https://github.com/cvfosammmm/setzer')
        self.about_dialog.set_authors(('Robert Griesel',))
        
        logo = Gtk.Image.new_from_file('./resources/images/org.setzer.setzer.svg')
        self.about_dialog.set_logo(logo.get_pixbuf())
        
        self.about_dialog.show_all()
        
    def on_appmenu_quit(self, action=None, parameter=''):
        ''' quit application, show save dialog if unsaved worksheets present. '''

        if not self.on_window_close(self.main_window):
            self.quit()
        
    def setup_hamburger_menu(self):
        self.add_action(self.workspace_controller.save_as_action)
        self.add_action(self.workspace_controller.save_all_action)
        self.add_action(self.workspace_controller.find_action)
        self.add_action(self.workspace_controller.find_next_action)
        self.add_action(self.workspace_controller.find_prev_action)
        self.add_action(self.workspace_controller.find_replace_action)
        self.add_action(self.workspace_controller.close_document_action)
        self.add_action(self.workspace_controller.close_all_action)
        self.add_action(self.workspace_controller.insert_before_after_action)
        self.add_action(self.workspace_controller.insert_symbol_action)
        self.add_action(self.workspace_controller.document_wizard_action)
        
    def toggle_dark_mode(self, action, parameter=None):
        new_state = not action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(new_state))
        self.settings.gtksettings.get_default().set_property('gtk-application-prefer-dark-theme', new_state)
        self.settings.set_value('preferences', 'prefer_dark_mode', new_state)
    

main_controller = MainApplicationController()
exit_status = main_controller.run(sys.argv)
sys.exit(exit_status)