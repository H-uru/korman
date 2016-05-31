/* This file is part of Korman.
 *
 * Korman is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Korman is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Korman.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "sound.h"

#include <PRP/Audio/plSoundBuffer.h>
#include <Stream/hsStream.h>
#include <vorbis/vorbisfile.h>

static const int BITS_PER_SAMPLE = 16;

extern "C" {

typedef struct {
    PyObject_HEAD
    hsStream* fThis;
    bool fPyOwned;
} pyStream;

typedef struct {
    PyObject_HEAD
    plWAVHeader* fThis;
    bool fPyOwned;
} pyWAVHeader;

static size_t _read_stream(void* ptr, size_t size, size_t nmemb, void* datasource) {
    hsStream* s = static_cast<hsStream*>(datasource);
    // hsStream is a bit overzealous protecting us against overreads, so we need to
    // make sure to not tick it off.
    size_t request = nmemb * size;
    size_t remaining = s->size() - s->pos();
    size_t min = std::min(request, remaining);
    if (min == 0) {
        return 0;
    } else {
        size_t read = s->read(min, ptr);
        return read / size;
    }
}

static int _seek_stream(void* datasource, ogg_int64_t offset, int whence) {
    hsStream* s = static_cast<hsStream*>(datasource);
    switch (whence) {
    case SEEK_CUR:
        s->skip(offset);
        break;
    case SEEK_SET:
        s->seek(offset);
        break;
    case SEEK_END:
        s->seek(s->size() - offset);
        break;
    }
    return 0;
}

static long _tell_stream(void* datasource) {
    hsStream* s = static_cast<hsStream*>(datasource);
    return s->pos();
}

static ov_callbacks s_callbacks = {
    (size_t(*)(void *, size_t, size_t, void *))_read_stream,
    (int (*)(void *, ogg_int64_t, int))_seek_stream,
    (int (*)(void *))NULL,
    (long (*)(void *))_tell_stream,
};

PyObject* inspect_vorbisfile(PyObject*, PyObject* args) {
    pyStream* stream;
    pyWAVHeader* header;
    if (!PyArg_ParseTuple(args, "OO", &stream, &header)) {
        PyErr_SetString(PyExc_TypeError, "inspect_vorbisfile expects an hsStream, plWAVHeader");
        return NULL;
    }

    // The OGG file may actually be in Blender's memory, so we will use hsStream. Therefore,
    // we must tell vorbisfile how to do this.
    OggVorbis_File vorbis;
    int result = ov_open_callbacks(stream->fThis, &vorbis, NULL, 0, s_callbacks);
    if (result < 0) {
        PyErr_Format(PyExc_RuntimeError, "vorbisfile ov_open_callbacks: %d", result);
        return NULL;
    }

    header->fThis->setFormatTag(plWAVHeader::kPCMFormatTag);
    header->fThis->setBitsPerSample(BITS_PER_SAMPLE);
    vorbis_info* info = ov_info(&vorbis, -1);
    header->fThis->setNumChannels(info->channels);
    header->fThis->setNumSamplesPerSec(info->rate);
    unsigned short align = (BITS_PER_SAMPLE * info->channels) >> 3;
    header->fThis->setBlockAlign(align);
    header->fThis->setAvgBytesPerSec(info->rate * align);

    // This behavior was copied and pasted from CWE
    ogg_int64_t size = (ov_pcm_total(&vorbis, -1) - 1) * align;

    // Cleanup
    ov_clear(&vorbis);

    // We got the plWAVHeader from Python because we don't link against PyHSPlasma, only libHSPlasma
    // Therefore, we only need to return the size.
    return PyLong_FromSsize_t(size);
}

};
