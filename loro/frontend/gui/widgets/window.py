# Copyright 2023 Vlad Krupinskii <mrvladus@yandex.ru>
# SPDX-License-Identifier: MIT

from __future__ import annotations
from gi.repository import Gio, Adw, Gtk  # type:ignore

from loro.frontend.gui.gsettings import GSettings
from loro.frontend.gui.factory import WidgetFactory
from loro.frontend.gui.actions import WidgetActions
from loro.frontend.gui.models import Item
from loro.frontend.gui.widgets.columnview import ColumnView
from loro.frontend.gui.widgets.views import ColumnViewToken
from loro.backend.core.env import ENV
from loro.backend.core.util import json_load
from loro.backend.core.log import get_logger
from loro.backend.services.nlp.spacy import explain_term

WINDOW: Window = None


class Window(Adw.ApplicationWindow):
    about_window: Adw.AboutWindow = None

    def __init__(self, **kwargs) -> None:
        self.log = get_logger('Window')
        super().__init__(**kwargs)
        self.app = kwargs['application']
        global WINDOW
        WINDOW = self
        self.actions = WidgetActions(self.app)
        self.factory = WidgetFactory(self.app)
        self.selected = []
        self._build_ui()
        self._update_ui()
        self.present()

    def _build_ui(self):
        self.set_title(_("Loro"))
        # ~ self.props.width_request = 1024
        # ~ self.props.height_request = 768
        # ~ # Remember window state
        # ~ GSettings.bind("width", self, "default_width")
        # ~ GSettings.bind("height", self, "default_height")
        # ~ GSettings.bind("maximized", self, "maximized")
        # Setup theme
        # ~ Adw.StyleManager.get_default().set_color_scheme(GSettings.get("theme"))

        mainbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Headerbar
        headerbar = Adw.HeaderBar()
        viewstack = Adw.ViewStack()
        viewstack.add_titled(Gtk.Label.new('Dictionary'), 'dictionary', 'Dictionary')
        viewstack.add_titled(Gtk.Label.new('Preferences'), 'preferences', 'Preferences')
        viewswitcher = Adw.ViewSwitcher()
        viewswitcher.set_stack(viewstack)
        # ~ headerbar.set_title_widget(viewswitcher) # It works, but it is disabled by now
        mainbox.append(headerbar)

        # Toolbox
        toolbox = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
        toolbox.set_margin_top(margin=6)
        toolbox.set_margin_end(margin=6)
        toolbox.set_margin_bottom(margin=6)
        toolbox.set_margin_start(margin=6)

        self.ddTopics = self.factory.create_dropdown_generic(Item, enable_search=True)
        self.ddTopics.connect("notify::selected-item", self._on_topic_selected)
        self.ddTopics.set_hexpand(False)
        toolbox.append(self.ddTopics)

        self.ddSubtopics = self.factory.create_dropdown_generic(Item, enable_search=True)
        self.ddSubtopics.connect("notify::selected-item", self._on_subtopic_selected)
        self.ddSubtopics.set_hexpand(False)
        toolbox.append(self.ddSubtopics)

        self.ddPos = self.factory.create_dropdown_generic(Item, enable_search=True)
        self.ddPos.connect("notify::selected-item", self._on_pos_selected)
        self.ddPos.set_hexpand(False)
        toolbox.append(self.ddPos)

        mainbox.append(toolbox)

        # Content View
        contentview = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, vexpand=True)
        contentview.set_margin_top(margin=6)
        contentview.set_margin_end(margin=6)
        contentview.set_margin_bottom(margin=6)
        contentview.set_margin_start(margin=6)
        self.cvleft = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL, hexpand=False, vexpand=True)
        # ~ cvleft.props.width_request = 400
        cvright = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL, hexpand=False, vexpand=True)
        cvrightup = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        cvrightdown = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)

        contentview.append(self.cvleft)
        contentview.append(cvright)
        cvright.append(cvrightup)
        cvright.append(cvrightdown)
        mainbox.append(contentview)

        self.cvtokens = ColumnViewToken(self.app)
        selection = self.cvtokens.get_selection()
        selection.connect('selection-changed', self._on_tokens_selected)
        self.cvleft.append(self.cvtokens)
        cvrightup.append(Gtk.Label.new('right up'))
        cvrightup.append(Gtk.Label.new('right down'))

        self.set_content(mainbox)

    def _on_tokens_selected(self, selection, position, n_items):
        self.selected_items = []
        model = selection.get_model()
        bitset = selection.get_selection()
        for index in range(bitset.get_size()):
            pos = bitset.get_nth(index)
            item = model.get_item(pos)
            self.log.info("%s > %s", item.id, item.title)
            self.selected_items.append(item)
        self.log.info("%d / %d" % (len(self.selected_items), len(model)))

    def _on_topic_selected(self, *args):
        item = self.ddTopics.get_selected_item()
        topic = item.id
        topics = self.app.dictionary.get_topics()
        self.log.debug("Displaying subtopics for topic '%s'", topic)
        data = []
        data.append(("ALL", "All subtopics"))
        if topic == "ALL":
            all_subs = set()
            for topic in topics:
                for subtopic in topics[topic]:
                    all_subs.add(subtopic)
            for subtopic in all_subs:
                data.append((subtopic.upper(), subtopic.title()))
        else:
            subtopics = topics[topic]
            for subtopic in subtopics:
                data.append((subtopic, subtopic.title()))
        self.actions.dropdown_populate(self.ddSubtopics, Item, data)

        if len(self.ddSubtopics.get_model()) > 0:
            self.ddSubtopics.set_selected(0)

    def _on_subtopic_selected(self, dropdown, gparam):
        item_topic = self.ddTopics.get_selected_item()
        item_subtopic = dropdown.get_selected_item()
        if item_topic is not None:
            topic = item_topic.id
        else:
            return
        if item_subtopic is not None:
            subtopic = item_subtopic.id
        else:
            return

        selected = []
        tokens = self.app.dictionary.get_tokens()
        for key in tokens.keys():
            if topic == 'ALL':
                if subtopic == 'ALL':
                    selected.append(key)
                else:
                    if subtopic in tokens[key]['subtopics']:
                        selected.append(key)
            else:
                if topic in tokens[key]['topics']:
                    if subtopic == 'ALL':
                        selected.append(key)
                    else:
                        if subtopic in tokens[key]['subtopics']:
                            selected.append(key)

        self.selected = selected
        self.log.info("Selected %d tokens for topic '%s' and subtopic '%s'", len(selected), topic, subtopic)

        # Update POS
        postags = set()
        for key in self.selected:
            for postag in tokens[key]['postags']:
                postags.add(postag)

        data = []
        data.append(("ALL", "All Part-Of-Speech tags"))
        for postag in postags:
            title = explain_term(postag).title()
            data.append((postag, explain_term(postag).title()))
        self.actions.dropdown_populate(self.ddPos, Item, data)

        # ~ self.actions.dropdown_populate(self.ddPos, Item, data)

        # ~ if matches:
        # ~ if len(dropdown.get_model()) > 0:
            # ~ # This is necessary. When Topic selection changes, subtopics
            # ~ # dropdown has no items and this fails

            # ~ items = []

            # ~ for key in tokens.keys():


    def _on_pos_selected(self, dropdown, gparam):
        tokens = self.app.dictionary.get_tokens()
        if len(dropdown.get_model()) > 0:
            item_postag = dropdown.get_selected_item()
            postag = item_postag.id
            selected = []
            for key in self.selected:
                if postag == 'ALL':
                    selected.append(key)
                else:
                    if postag in tokens[key]['postags']:
                        selected.append(key)

            items = []
            lenmax = 0
            for key in selected:
                lemma = tokens[key]['lemmas'][0]
                items.append(Item(id=key, title=key))
                if len(key) > lenmax:
                    lenmax = len(key)
            self.cvtokens.update(items)
            self.log.info("Selected %d tokens for POS tag '%s'", len(selected), postag)
            if lenmax < 25:
                lenmax = 25
            self.cvleft.props.width_request = lenmax*8


    def _update_ui(self):
        # ~ # Update topics
        topics = self.app.dictionary.get_topics()
        data = []
        data.append(("ALL", "All topics"))
        for topic in topics.keys():
            data.append((topic.upper(), topic.title()))
        self.actions.dropdown_populate(self.ddTopics, Item, data)

        # ~ # Update P-O-S
        # ~ fpos = self.app.dictionary.get_file_pos()
        # ~ adict = json_load(fpos)
        # ~ data = []
        # ~ for key in adict.keys():
            # ~ title = explain_term(key).title()
            # ~ data.append((key, title))
        # ~ self.actions.dropdown_populate(self.ddPos, Item, data)

