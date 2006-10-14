import os
import shutil
import unittest


import wibbrlib


class IoBase(unittest.TestCase):

    def setUp(self):
        self.cachedir = "tmp.cachedir"
        self.rootdir = "tmp.rootdir"
        
        os.mkdir(self.cachedir)
        os.mkdir(self.rootdir)
        
        config_list = (
            ("wibbr", "cache-dir", self.cachedir),
            ("wibbr", "local-store", self.rootdir)
        )
    
        self.context = wibbrlib.context.create()
    
        for section, item, value in config_list:
            if not self.context.config.has_section(section):
                self.context.config.add_section(section)
            self.context.config.set(section, item, value)

        self.context.cache = wibbrlib.cache.init(self.context.config)
        self.context.be = wibbrlib.backend.init(self.context.config, 
                                                self.context.cache)

    def tearDown(self):
        shutil.rmtree(self.cachedir)
        shutil.rmtree(self.rootdir)
        del self.cachedir
        del self.rootdir
        del self.context


class ObjectQueueFlushing(IoBase):

    def testFlushing(self):
        wibbrlib.obj.object_queue_add(self.context.oq, "pink", "pretty")
        
        self.failUnlessEqual(wibbrlib.backend.list(self.context.be), [])
        
        wibbrlib.io.flush_object_queue(self.context)

        list = wibbrlib.backend.list(self.context.be)
        self.failUnlessEqual(len(list), 1)
        
        b1 = [os.path.basename(x) 
                for x in wibbrlib.mapping.get(self.context.map, "pink")]
        b2 = [os.path.basename(x) for x in list]
        self.failUnlessEqual(b1, b2)


class GetObjectTests(IoBase):

    def upload_object(self, object_id, object):
        wibbrlib.obj.object_queue_add(self.context.oq, object_id, object)
        wibbrlib.io.flush_object_queue(self.context)

    def testGetObject(self):
        id = "pink"
        component = wibbrlib.cmp.create(42, "pretty")
        object = wibbrlib.obj.create(id, 0)
        wibbrlib.obj.add(object, component)
        object = wibbrlib.obj.encode(object)
        self.upload_object(id, object)
        o = wibbrlib.io.get_object(self.context, id)

        self.failUnlessEqual(wibbrlib.obj.get_id(o), id)
        self.failUnlessEqual(wibbrlib.obj.get_type(o), 0)
        list = wibbrlib.obj.get_components(o)
        self.failUnlessEqual(len(list), 1)
        self.failUnlessEqual(wibbrlib.cmp.get_type(list[0]), 42)
        self.failUnlessEqual(wibbrlib.cmp.get_string_value(list[0]), 
                             "pretty")


class HostBlock(IoBase):

    def testFetchHostBlock(self):
        host_id = self.context.config.get("wibbr", "host-id")
        host = wibbrlib.obj.host_block_encode(host_id, ["gen1", "gen2"],
                                                 ["map1", "map2"])
        be = wibbrlib.backend.init(self.context.config, self.context.cache)
        
        wibbrlib.io.upload_host_block(self.context, host)
        host2 = wibbrlib.io.get_host_block(self.context.be)
        self.failUnlessEqual(host, host2)
