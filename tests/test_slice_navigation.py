import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np
import xarray as xr

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QScrollBar

from cyto_studio.cyto_studio import CYTOSTUDIO


class SliceNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rapid_changes_load_only_final_slice(self):
        scroll = QScrollBar()
        scroll.setRange(1, 100)
        timer = QTimer(scroll)
        timer.setSingleShot(True)
        timer.setInterval(120)
        state = SimpleNamespace(scroll=scroll, image_slice=QLineEdit(),
                                loaded_2D=True, ignore_gui_call=False,
                                _slice_load_timer=timer)
        loaded = []
        timer.timeout.connect(lambda: loaded.append(scroll.value()))
        scroll.valueChanged.connect(lambda: CYTOSTUDIO.set_image_slice_value(state))
        for value in (2, 3, 4, 5):
            scroll.setValue(value)
            QTest.qWait(10)
        self.assertEqual(loaded, [])
        self.assertEqual(state.image_slice.text(), '5')
        QTest.qWait(200)
        self.assertEqual(loaded, [5])

    def test_non_2d_or_programmatic_changes_do_not_schedule_reads(self):
        state = SimpleNamespace(scroll=Mock(), image_slice=Mock(),
                                loaded_2D=False, ignore_gui_call=False,
                                _slice_load_timer=Mock())
        CYTOSTUDIO.set_image_slice_value(state)
        state.loaded_2D = True
        state.ignore_gui_call = True
        CYTOSTUDIO.set_image_slice_value(state)
        state._slice_load_timer.start.assert_not_called()

    def test_enter_loads_typed_slice_once_and_updates_scrollbar(self):
        scroll = QScrollBar()
        scroll.setRange(1, 100)
        timer = QTimer(scroll)
        timer.setSingleShot(True)
        timer.setInterval(120)
        state = SimpleNamespace(scroll=scroll, image_slice=QLineEdit(),
                                loaded_2D=True, ignore_gui_call=False,
                                _slice_load_timer=timer, _load_image_slice=Mock())
        scroll.valueChanged.connect(lambda: CYTOSTUDIO.set_image_slice_value(state))
        timer.timeout.connect(state._load_image_slice)
        state.image_slice.returnPressed.connect(lambda: CYTOSTUDIO.load_slice_from_text(state))
        state.image_slice.setText('42')
        QTest.keyClick(state.image_slice, Qt.Key_Return)
        self.assertEqual(scroll.value(), 42)
        self.assertEqual(state.image_slice.text(), '42')
        state._load_image_slice.assert_called_once_with()
        self.assertFalse(timer.isActive())
        QTest.qWait(200)
        state._load_image_slice.assert_called_once_with()

    def test_typed_slice_is_clamped_and_invalid_text_is_restored(self):
        scroll = QScrollBar()
        scroll.setRange(1, 100)
        state = SimpleNamespace(scroll=scroll, image_slice=QLineEdit(),
                                loaded_2D=True, ignore_gui_call=False,
                                _slice_load_timer=Mock(), _load_image_slice=Mock())
        for text, expected in (('999', 100), ('0', 1), ('-4', 1), (' 8 ', 8)):
            with self.subTest(text=text):
                state.image_slice.setText(text)
                CYTOSTUDIO.load_slice_from_text(state)
                self.assertEqual(scroll.value(), expected)
                self.assertEqual(state.image_slice.text(), str(expected))
        state._load_image_slice.reset_mock()
        for text in ('', 'abc', '1.5'):
            state.image_slice.setText(text)
            CYTOSTUDIO.load_slice_from_text(state)
            self.assertEqual(state.image_slice.text(), '8')
        state._load_image_slice.assert_not_called()

    def test_odd_and_even_navigation_updates_only_selected_channels(self):
        for odd, even, expected_section in ((False, False, 'S002'),
                                             (True, False, 'S003'),
                                             (False, True, 'S004')):
            with self.subTest(odd=odd, even=even):
                reader = SimpleNamespace(channel_names=['A', 'B'],
                                         sections=['S001', 'S002', 'S003', 'S004'],
                                         multiscale_planes=Mock(return_value=['pyramid']))
                layer = SimpleNamespace(name='B', data=None)

                class Layers(list):
                    def __getitem__(self, key):
                        return layer if key == 'B' else super().__getitem__(key)

                state = SimpleNamespace(
                    loaded_2D=True, ignore_gui_call=False, image_slice=Mock(),
                    scroll=Mock(value=Mock(return_value=2)),
                    cb_Odd_slice=Mock(isChecked=Mock(return_value=odd)),
                    cb_Even_slice=Mock(isChecked=Mock(return_value=even)),
                    optical_slices_available=1,
                    data=SimpleNamespace(is_sd=True, sd=reader),
                    selected_channels=[1], viewer=SimpleNamespace(layers=Layers([layer])),
                )
                CYTOSTUDIO._load_image_slice(state)
                reader.multiscale_planes.assert_called_once_with(expected_section, 1)
                self.assertEqual(layer.data, ['pyramid'])

    def test_legacy_navigation_uses_current_section_scaling(self):
        first = xr.DataArray(np.ones((1, 4, 4)), dims=('channel', 'y', 'x'),
                             coords={'channel': ['A']}, attrs={'bscale': 1, 'bzero': 0})
        second = first.copy()
        second.attrs = {'bscale': 4, 'bzero': 3}
        dataset = xr.Dataset({'S001': first, 'S002': second})
        data = SimpleNamespace(is_sd=False,
                               **{name: dataset for name in
                                  ('ds1', 'ds2', 'ds4', 'ds8', 'ds16', 'ds32')})
        layer = SimpleNamespace(name='A', data=None)

        class Layers(list):
            def __getitem__(self, key):
                return layer if key == 'A' else super().__getitem__(key)

        state = SimpleNamespace(
            loaded_2D=True, ignore_gui_call=False, image_slice=Mock(), old_method=False,
            scroll=Mock(value=Mock(return_value=2)),
            cb_Odd_slice=Mock(isChecked=Mock(return_value=False)),
            cb_Even_slice=Mock(isChecked=Mock(return_value=False)),
            optical_slices_available=1, data=data, selected_channels=[0],
            viewer=SimpleNamespace(layers=Layers([layer])),
        )
        CYTOSTUDIO._load_image_slice(state)
        self.assertEqual(len(layer.data), 6)
        for plane in layer.data:
            np.testing.assert_array_equal(plane, np.full((4, 4), 7))


if __name__ == '__main__':
    unittest.main()
