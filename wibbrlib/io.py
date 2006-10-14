"""Module for doing local file I/O and higher level remote operations"""


import wibbrlib


def flush_object_queue(be, map, oq):
    """Put all objects in an object queue into a block and upload it
    
    Also put mappings into map.
    
    """
    
    block_id = wibbrlib.backend.generate_block_id(be)
    block = wibbrlib.obj.block_create_from_object_queue(block_id, oq)
    wibbrlib.backend.upload(be, block_id, block)
    for id in wibbrlib.obj.object_queue_ids(oq):
        wibbrlib.mapping.add(map, id, block_id)


def get_block(be, block_id):
    """Get a block from cache or by downloading it"""
    block = wibbrlib.cache.get_block(be.cache, block_id)
    if not block:
        e = wibbrlib.backend.download(be, block_id)
        if e:
            raise e
        block = wibbrlib.cache.get_block(be.cache, block_id)
    return block


class MissingBlock(wibbrlib.exception.WibbrException):

    def __init__(self, block_id, object_id):
        self._msg = "Block %s for object %s is missing" % \
                        (block_id, object_id)


def find_components_by_type(components, wanted_type):
    """Find all components of a given type"""
    return [x for x in components 
                if wibbrlib.cmp.get_type(x) == wanted_type]


def create_object_from_component_list(components):
    """Create a new object from a list of components"""
    list = find_components_by_type(components, wibbrlib.cmp.CMP_OBJID)
    assert len(list) == 1
    id = wibbrlib.cmp.get_string_value(list[0])
    
    list = find_components_by_type(components, wibbrlib.cmp.CMP_OBJTYPE)
    assert len(list) == 1
    type = wibbrlib.cmp.get_string_value(list[0])
    (type, _) = wibbrlib.varint.decode(type, 0)

    o = wibbrlib.obj.create(id, type)
    bad = (wibbrlib.cmp.CMP_OBJID,
           wibbrlib.cmp.CMP_OBJTYPE)
    for c in components:
        if wibbrlib.cmp.get_type(c) not in bad:
            wibbrlib.obj.add(o, c)
    return o


def get_object(be, map, object_id):
    """Fetch an object"""
    block_ids = wibbrlib.mapping.get(map, object_id)
    if not block_ids:
        return None
    assert len(block_ids) == 1
    block_id = block_ids[0]
    block = get_block(be, block_id)
    if not block:
        raise MissingBlock(block_id, object_id)
    list = wibbrlib.cmp.decode_all(block, 0)
    list = find_components_by_type(list, wibbrlib.cmp.CMP_OBJPART)
    for component in list:
        subs = wibbrlib.cmp.get_subcomponents(component)
        objids = find_components_by_type(subs,
                                         wibbrlib.cmp.CMP_OBJID)
        objids = [wibbrlib.cmp.get_string_value(x) for x in objids]
        objids = [x for x in objids if x == object_id]
        if objids:
            return create_object_from_component_list(subs)
    return None


def upload_host_block(be, host_block):
    """Upload a host block"""
    return wibbrlib.backend.upload(be, be.config.get("wibbr", "host-id"), 
                                   host_block)


def get_host_block(be):
    """Return (and fetch, if needed) the host block, or None if not found"""
    host_id = be.config.get("wibbr", "host-id")
    e = wibbrlib.backend.download(be, host_id)
    if e:
        raise e
    return wibbrlib.cache.get_block(be.cache, host_id)
