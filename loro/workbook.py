#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import pprint


from spacy.tokens import Token

from loro.backend.core.env import ENV
from loro.backend.core.log import get_logger
from loro.backend.core.util import json_load, json_save
from loro.backend.core.util import get_project_config_dir
from loro.dictionary import Dictionary


class Workbook:
    def __init__(self):
        self.log = get_logger('Workbook')

    def get_dictionary(self, workbook):
        return Dictionary(workbook)

    def get_all(self):
        source, target = ENV['Projects']['Default']['Languages']
        config_dir = get_project_config_dir(source)
        workbooks_path = os.path.join(config_dir, 'workbooks.json')
        if not os.path.exists(workbooks_path):
            return {}
        return json_load(workbooks_path)

    def get_files(self, wbname):
        return self.get_all()[wbname]

    def exists(self, name: str) -> bool:
        return name.upper() in self.get_all().keys()

    def add(self, name: str) -> None:
        workbooks = self.get_all()
        workbooks[name.upper()] = []
        self._save(workbooks)
        self.log.debug("Workbook '%s' added", name)

    def rename(self, old_name: str, new_name: str) -> bool:
        workbooks = self.get_all()
        workbooks[new_name.upper()] = workbooks[old_name]
        del(workbooks[old_name])
        self._save(workbooks)
        self.log.debug("Workbook '%s' renamed to '%s'", old_name, new_name)

    def update(self, wbname:str, fname:str, active:bool):
        workbooks = self.get_all()
        try:
            fnames = workbooks[wbname]
        except:
            return

        changes = False
        if active:
            if not fname in fnames:
                fnames.append(fname)
                workbooks[wbname] = fnames
                changes = True
        else:
            if fname in fnames:
                fnames.remove(fname)
                workbooks[wbname] = fnames
                changes = True

        if changes:
            self._save(workbooks)

    def have_file(self, wbname: str, fname: str) -> bool:
        return fname in self.get_all()[wbname]

    def delete(self, name:str) -> None:
        if self.exists(name):
            workbooks = self.get_all()
            del(workbooks[name])
            self._save(workbooks)
            self.log.debug("Workbook '%s' deleted", name)

    def _save(self, workbooks):
        source, target = ENV['Projects']['Default']['Languages']
        config_dir = get_project_config_dir(source)
        workbooks_path = os.path.join(config_dir, 'workbooks.json')
        json_save(workbooks_path, workbooks)
        self.log.debug("%d workbooks saved", len(workbooks))