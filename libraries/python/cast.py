import struct

castHashBase = 0x534E495752545250


def castNextHash():
    global castHashBase

    hash = castHashBase
    castHashBase += 1

    return hash


class CastString_t(object):
    __slots__ = ("value")

    def __init__(self, file=None):
        self.value = ""

        if file is not None:
            self.load(file)

    def load(self, file):
        bytes = b''
        b = file.read(1)
        while not b == b'\x00':
            bytes += b
            b = file.read(1)
        self.value = bytes.decode("utf-8")

    def save(self, file):
        file.write(self.value.encode("utf-8"))
        file.write(b'\x00')


class CastProperty_t(object):
    __slots__ = ("size", "fmt", "identifier", "array")

    def __init__(self, identifier=None):
        switcher = {
            'b': [1, "B", 1],
            'h': [2, "H", 1],
            'i': [4, "I", 1],
            'l': [8, "Q", 1],
            'f': [4, "f", 1],
            'd': [8, "d", 1],
            's': [0, "s", 1],
            '2v': [8, "2f", 2],
            '3v': [12, "3f", 3],
            '4v': [16, "4f", 4]
        }

        if identifier is None:
            self.size = 0
            self.fmt = ""
            self.identifier = None
            self.array = 1
            return

        self.size = switcher[identifier][0]
        self.fmt = switcher[identifier][1]
        self.array = switcher[identifier][2]
        self.identifier = identifier


class CastProperty(object):
    __slots__ = ("name", "type", "values")

    def __init__(self, file=None):
        self.name = ""
        self.type = CastProperty_t()
        self.values = []

        if file is not None:
            self.load(file)

    def load(self, file):
        header = struct.unpack("2sHI", file.read(0x8))

        self.name = struct.unpack(("%ds" % header[1]), file.read(header[1]))[
            0].decode("utf-8")
        self.type = CastProperty_t(header[0].decode("utf-8").strip('\0'))

        if (self.type.size == 0 and self.type.fmt == "s"):
            self.values = [CastString_t(file).value]
        else:
            self.values = [None] * header[2]
            self.values = struct.unpack(
                self.type.fmt * header[2], file.read(self.type.size * header[2]))

    def save(self, file):
        identifier = self.type.identifier.encode("utf-8")
        name = self.name.encode("utf-8")

        file.write(struct.pack(
            "2sHI", identifier, len(name), int(len(self.values) / self.type.array)))
        file.write(name)

        if self.type.size == 0 and self.type.fmt == "s":
            string = CastString_t()
            string.value = self.values[0]

            string.save(file)
        else:
            file.write(struct.pack(self.type.fmt *
                       int(len(self.values) / self.type.array), *self.values))

    def length(self):
        result = 0x8

        result += len(self.name.encode("utf-8"))

        if self.type.size == 0 and self.type.fmt == "s":
            result += len(self.values[0].encode("utf-8")) + 1
        else:
            result += self.type.size * int(len(self.values) / self.type.array)

        return result


class CastNode(object):
    __slots__ = ("identifier", "hash", "parentNode",
                 "childNodes", "properties")

    def __init__(self, identifier=0):
        self.childNodes = []
        self.properties = {}
        self.identifier = identifier
        self.hash = castNextHash()
        self.parentNode = None

    def ChildrenOfType(self, pType):
        return [x for x in self.childNodes if x.__class__ is pType]

    def ChildByHash(self, hash):
        find = [x for x in self.childNodes if x.hash == hash]
        if len(find) > 0:
            return find[0]
        return None

    def Hash(self):
        return self.hash

    @staticmethod
    def load(file):
        header = struct.unpack("IIQII", file.read(0x18))

        if header[0] in typeSwitcher:
            node = typeSwitcher[header[0]]()
        else:
            node = typeSwitcher[None]()

        node.identifier = header[0]
        node.childNodes = [None] * header[4]
        node.hash = header[2]

        for i in range(header[3]):
            prop = CastProperty(file)
            node.properties[prop.name] = prop
        for i in range(header[4]):
            node.childNodes[i] = CastNode.load(file)
            node.childNodes[i].parentNode = node

        return node

    def save(self, file):
        file.write(struct.pack("IIQII", self.identifier, self.length(),
                   self.hash, len(self.properties), len(self.childNodes)))

        for property in self.properties.values():
            property.save(file)
        for childNode in self.childNodes:
            childNode.save(file)

    def length(self):
        result = 0x18

        for property in self.properties.values():
            result += property.length()
        for childNode in self.childNodes:
            result += childNode.length()

        return result


class Model(CastNode):
    def __init__(self):
        super(Model, self).__init__(0x6C646F6D)

    def Skeleton(self):
        find = self.ChildrenOfType(Skeleton)
        if len(find) > 0:
            return find[0]
        return None

    def Meshes(self):
        return self.ChildrenOfType(Mesh)

    def Materials(self):
        return self.ChildrenOfType(Material)

    def BlendShapes(self):
        return self.ChildrenOfType(BlendShape)


class Animation(CastNode):
    def __init__(self):
        super(Animation, self).__init__(0x6D696E61)

    def Skeleton(self):
        find = self.ChildrenOfType(Skeleton)
        if len(find) > 0:
            return find[0]
        return None

    def Curves(self):
        return self.ChildrenOfType(Curve)

    def Framerate(self):
        fr = self.properties.get("fr")
        if fr is not None:
            return fr.values[0]
        return None

    def Looping(self):
        lo = self.properties.get("lo")
        if lo is not None:
            return lo.values[0] == 1
        return False


class Curve(CastNode):
    def __init__(self):
        super(Curve, self).__init__(0x76727563)

    def NodeName(self):
        nn = self.properties.get("nn")
        if nn is not None:
            return nn.values[0]
        return None

    def KeyPropertyName(self):
        kp = self.properties.get("kp")
        if kp is not None:
            return kp.values[0]
        return None

    def KeyFrameBuffer(self):
        kb = self.properties.get("kb")
        if kb is not None:
            return kb.values
        return None

    def KeyValueBuffer(self):
        kv = self.properties.get("kv")
        if kv is not None:
            return kv.values
        return None

    def Mode(self):
        m = self.properties.get("m")
        if m is not None:
            return m.values[0]
        return None

    def AdditiveBlendWeight(self):
        ab = self.properties.get("ab")
        if ab is not None:
            return ab.values[0]
        return 1.0


class NotificationTrack(CastNode):
    def __init__(self):
        super(NotificationTrack, self).__init__(0x6669746E)

    def Name(self):
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def KeyFrameBuffer(self):
        kb = self.properties.get("kb")
        if kb is not None:
            return kb.values
        return None


class Mesh(CastNode):
    def __init__(self):
        super(Mesh, self).__init__(0x6873656D)

    def Name(self):
        n = self.properties.get("n")
        if n is not None:
            return n.values[0]
        return None

    def VertexCount(self):
        vp = self.properties.get("vp")
        if vp is not None:
            return len(vp.values) / 3

    def FaceCount(self):
        f = self.properties.get("f")
        if f is not None:
            return len(f.values) / 3

    def UVLayerCount(self):
        uc = self.properties.get("ul")
        if uc is not None:
            return uc.values[0]
        return 0

    def MaximumWeightInfluence(self):
        mi = self.properties.get("mi")
        if mi is not None:
            return mi.values[0]
        return 0

    def FaceBuffer(self):
        f = self.properties.get("f")
        if f is not None:
            return f.values
        return None

    def VertexPositionBuffer(self):
        vp = self.properties.get("vp")
        if vp is not None:
            return vp.values
        return None

    def VertexNormalBuffer(self):
        vn = self.properties.get("vn")
        if vn is not None:
            return vn.values
        return None

    def VertexTangentBuffer(self):
        vt = self.properties.get("vt")
        if vt is not None:
            return vt.values
        return None

    def VertexColorBuffer(self):
        vc = self.properties.get("vc")
        if vc is not None:
            return vc.values
        return None

    def VertexUVLayerBuffer(self, index):
        ul = self.properties.get("u%d" % index)
        if ul is not None:
            return ul.values
        return None

    def VertexWeightBoneBuffer(self):
        wb = self.properties.get("wb")
        if wb is not None:
            return wb.values
        return None

    def VertexWeightValueBuffer(self):
        wv = self.properties.get("wv")
        if wv is not None:
            return wv.values
        return None

    def Material(self):
        m = self.properties.get("m")
        if m is not None:
            return self.parentNode.ChildByHash(m.values[0])
        return None


class BlendShape(CastNode):
    def __init__(self):
        super(BlendShape, self).__init__(0x68736C62)

    def BaseShape(self):
        b = self.properties.get("b")
        if b is not None:
            return self.parentNode.ChildByHash(b.values[0])
        return None

    def TargetShapes(self):
        t = self.properties.get("t")
        if t is not None:
            return [self.parentNode.ChildByHash(x) for x in t.values]
        return None

    def TargetWeightScales(self):
        ts = self.properties.get("ts")
        if ts is not None:
            return ts.values
        return None


class Skeleton(CastNode):
    def __init__(self):
        super(Skeleton, self).__init__(0x6C656B73)

    def Bones(self):
        return self.ChildrenOfType(Bone)


class Bone(CastNode):
    def __init__(self):
        super(Bone, self).__init__(0x656E6F62)

    def Name(self):
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def ParentIndex(self):
        parent = self.properties.get("p")
        if parent is not None:
            # Since cast uses unsigned types, we must
            # convert to a signed integer, as the range is -1 - INT32_MAX
            parentUnsigned = parent.values[0]
            parentUnsigned = parentUnsigned & 0xffffffff
            return (parentUnsigned ^ 0x80000000) - 0x80000000
        return -1

    def SegmentScaleCompensate(self):
        ssc = self.properties.get("ssc")
        if ssc is not None:
            return ssc.values[0] == 1
        return None

    def LocalPosition(self):
        localPos = self.properties.get("lp")
        if localPos is not None:
            return localPos.values
        return None

    def LocalRotation(self):
        localRot = self.properties.get("lr")
        if localRot is not None:
            return localRot.values
        return None

    def WorldPosition(self):
        worldPos = self.properties.get("wp")
        if worldPos is not None:
            return worldPos.values
        return None

    def WorldRotation(self):
        worldRot = self.properties.get("wr")
        if worldRot is not None:
            return worldRot.values
        return None

    def Scale(self):
        scale = self.properties.get("s")
        if scale is not None:
            return scale.values
        return None


class Material(CastNode):
    def __init__(self):
        super(Material, self).__init__(0x6C74616D)

    def Name(self):
        name = self.properties.get("n")
        if name is not None:
            return name.values[0]
        return None

    def Type(self):
        tp = self.properties.get("t")
        if tp is not None:
            return tp.values[0]
        return None

    def Slots(self):
        slots = {}
        for slot in self.properties:
            if slot != "n" and slot != "t":
                slots[slot] = self.ChildByHash(self.properties[slot].values[0])
        return slots


class File(CastNode):
    def __init__(self):
        super(File, self).__init__(0x656C6966)

    def Path(self):
        path = self.properties.get("p")
        if path is not None:
            return path.values[0]
        return None


typeSwitcher = {
    None: CastNode,
    0x6C646F6D: Model,
    0x6873656D: Mesh,
    0x68736C62: BlendShape,
    0x6C656B73: Skeleton,
    0x6D696E61: Animation,
    0x76727563: Curve,
    0x6669746E: NotificationTrack,
    0x656E6F62: Bone,
    0x6C74616D: Material,
    0x656C6966: File,
}


class Cast(object):
    __slots__ = ("rootNodes")

    def __init__(self):
        self.rootNodes = []

    def Roots(self):
        return [x for x in self.rootNodes]

    @staticmethod
    def load(path):
        try:
            file = open(path, "rb")
        except IOError:
            raise Exception("Could not open file for reading: %s\n" % path)

        header = struct.unpack("IIII", file.read(0x10))
        if header[0] != 0x74736163:
            raise Exception("Invalid cast file magic")

        cast = Cast()
        cast.rootNodes = [None] * header[2]

        for i in range(header[2]):
            cast.rootNodes[i] = CastNode.load(file)

        return cast

    def save(self, path):
        try:
            file = open(path, "wb")
        except IOError:
            raise Exception("Could not create file for writing: %s\n" % path)

        file.write(struct.pack(
            "IIII", 0x74736163, 0x1, len(self.rootNodes), 0))

        for rootNode in self.rootNodes:
            rootNode.save(file)