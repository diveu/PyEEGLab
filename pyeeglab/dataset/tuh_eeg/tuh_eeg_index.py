from ...database.index import BaseTable, File, EDFMeta, Index

import os
import uuid
import json
import warnings
import mne
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TUHEEGCorpusIndex(Index):
    def __init__(self, path):
        self._logger.debug('Create TUH EEG Corpus Index')
        super().__init__(path)
        self._logger.debug('Redirect MNE logging interface to file')
        mne.set_log_file(os.path.join(path, 'mne.log'), overwrite=False)
        self._logger.debug('Disable MNE runtime warnings')
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        self.loadIndex()
        self.indexFiles()

    def getFilesFromPath(self, path):
        self._logger.debug('Get files from path')
        files = []
        for dirpath, dirnames, filenames in os.walk(path):
            for file in filenames:
                if not file.endswith('.db') and not file.endswith('.log'):
                    files.append(os.path.join(dirpath, file))
        return files

    def getMetadataFromFile(self, path, file):
        meta = file[len(path):].split(os.path.sep)
        metadata = {
            'id': str(uuid.uuid5(uuid.NAMESPACE_X500, file[len(path):])),
            'type': meta[1],
            'eeg_class': meta[2],
            'patient_id': meta[5],
            'session_id': meta[6],
            'format': meta[-1].split('.')[-1],
            'path': file[len(path):],
        }
        return metadata

    def loadIndex(self):
        path = 'sqlite:///' + os.path.join(self.path(), 'index.db')
        self._logger.debug('Load index at %s', path)
        engine = create_engine(path)
        BaseTable.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self._db = Session()

    def indexFiles(self):
        self._logger.debug('Index files')
        files = self.getFilesFromPath(self.path())
        for file in files:
            f = File(self.getMetadataFromFile(self.path(), file))
            stm = self.db().query(File).filter(File.id == f.id).all()
            if len(stm) == 0:
                self._logger.debug('Add file %s at %s to index', f.id, f.path)
                self.db().add(f)
                if f.format == 'edf':
                    path = os.path.join(self.path(), f.path)
                    with mne.io.read_raw_edf(path) as r:
                        m = EDFMeta({
                            'id': f.id,
                            'file_duration': r.n_times/r.info['sfreq'],
                            'signal_count': r.info['nchan'],
                            'frequency': r.info['sfreq'],
                            'channels': json.dumps(r.info['ch_names']),
                        })
                        self._logger.debug('Add file %s edf metada to index', f.id)
                        self.db().add(m)
        self._logger.debug('Index files completed')
        self.db().commit()
