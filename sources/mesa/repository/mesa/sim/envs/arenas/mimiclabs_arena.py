from robosuite.models.arenas import TableArena

from mesa.sim.envs.arenas.style import get_texture_path


class MimicLabsTableArena(TableArena):
    """
    Workspace that contains an empty table.


    Args:
        table_full_size (3-tuple): (L,W,H) full dimensions of the table
        table_friction (3-tuple): (sliding, torsional, rolling) friction parameters of the table
        table_offset (3-tuple): (x,y,z) offset from center of arena when placing table.
            Note that the z value sets the upper limit of the table
        has_legs (bool): whether the table has legs or not
        xml (str): xml file to load arena
    """

    def __init__(
        self,
        floor_style="light-gray-floor-tile",
        wall_style="light-gray-plaster",
        # Optional: if provided, rewrites the table texture(s) in the scene XML.
        # (We keep it optional to avoid changing existing scene defaults.)
        table_style=None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        texplane = self.asset.find("./texture[@name='texplane']")
        plane_file = get_texture_path(type_name="floor", style=floor_style)
        texplane.set("file", plane_file)

        texwall = self.asset.find("./texture[@name='tex-wall']")
        wall_file = get_texture_path(type_name="wall", style=wall_style)
        texwall.set("file", wall_file)

        if table_style is not None:
            # Table top / body texture
            textable = self.asset.find("./texture[@name='tex-table']")
            if textable is not None:
                table_file = get_texture_path(type_name="table", style=table_style)
                textable.set("file", table_file)
