import colander
import deform.widget

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from dnascissors.model import Project

from webapp.plots.plotter import Plotter
from webapp.plots.ngsplotter import NGSPlotter


# See http://docs.pylonsproject.org/projects/pyramid/en/latest/quick_tutorial/forms.html
# File uploads: http://docs.pylonsproject.org/projects/pyramid-cookbook/en/latest/forms/file_uploads.html

class ProjectContent(colander.MappingSchema):
    comments = colander.SchemaNode(colander.String(), title="comments")


class ProjectViews(object):

    def __init__(self, request):
        self.request = request
        self.dbsession = request.dbsession

    def projects_form(self, buttonTitle):
        schema = ProjectContent().bind(request=self.request)
        submitButton = deform.form.Button(name='submit', title=buttonTitle)
        return deform.Form(schema, buttons=(submitButton,))

    @view_config(route_name="project_view", renderer="../templates/project/viewproject.pt")
    def view_project(self):
        id = self.request.matchdict['projectid']
        project = self.dbsession.query(Project).filter(Project.id == id).one()
        plotter = Plotter(self.dbsession, project.geid)
        ngsplotter = NGSPlotter(self.dbsession, project.geid)
        # Project table
        project_headers = [
            "geid",
            "name",
            "scientist",
            "group leader",
            "group",
            "start date",
            "end date",
            "description",
            "comments",
            "abundance data",
            "growth data",
            "ngs data"]
        project_rows = [[project.geid,
                        project.name,
                        project.scientist,
                        project.group_leader,
                        project.group,
                        project.start_date,
                        project.end_date,
                        project.description,
                        project.comments,
                        project.is_abundance_data_available,
                        project.is_growth_data_available,
                        project.is_variant_data_available]]
        # Target table
        targets = project.targets
        target_headers = [
            "name",
            "species",
            "assembly",
            "gene",
            "chromosome",
            "start",
            "end",
            "strand",
            "description"]
        target_rows = []
        guide_rows = []
        guide_mismatch_rows = []
        for target in targets:
            row = []
            row.append(target.name)
            row.append(target.genome.species)
            row.append(target.genome.assembly)
            row.append(target.gene_id)
            row.append(target.chromosome)
            row.append(target.start)
            row.append(target.end)
            row.append(target.strand)
            row.append(target.description)
            target_rows.append(row)
            for guide in target.guides:
                guide_row = []
                guide_row.append(target.name)
                guide_row.append(guide.genome.species)
                guide_row.append(guide.genome.assembly)
                guide_row.append(guide.name)
                guide_row.append(guide.guide_sequence)
                guide_row.append(guide.pam_sequence)
                guide_row.append(guide.activity)
                guide_row.append(guide.exon)
                guide_row.append(guide.nuclease)
                guide_rows.append(guide_row)
                mismatch_dict = {}
                mismatch_dict['genome region'] = "{} coding".format(guide.name)
                for mismatch in guide.guide_mismatches:
                    if mismatch.is_off_target_coding_region:
                        if mismatch.number_of_mismatches == 1:
                            mismatch_dict['1'] = mismatch.number_of_off_targets
                        elif mismatch.number_of_mismatches == 2:
                            mismatch_dict['2'] = mismatch.number_of_off_targets
                        elif mismatch.number_of_mismatches == 3:
                            mismatch_dict['3'] = mismatch.number_of_off_targets
                guide_mismatch_rows.append(mismatch_dict.values())
                mismatch_dict = {}
                mismatch_dict['genome region'] = "{} non-coding".format(guide.name)
                for mismatch in guide.guide_mismatches:
                    if not mismatch.is_off_target_coding_region:
                        if mismatch.number_of_mismatches == 1:
                            mismatch_dict['1'] = mismatch.number_of_off_targets
                        elif mismatch.number_of_mismatches == 2:
                            mismatch_dict['2'] = mismatch.number_of_off_targets
                        elif mismatch.number_of_mismatches == 3:
                            mismatch_dict['3'] = mismatch.number_of_off_targets
                guide_mismatch_rows.append(mismatch_dict.values())
        # Guide table
        guide_headers = [
            "target name",
            "species",
            "assembly",
            "guide name",
            "guide sequence",
            "pam sequence",
            "activity",
            "exon",
            "nuclease"
        ]
        # Guide mismatch table
        guide_mismatch_headers = [
            "genome region",
            "1",
            "2",
            "3"
        ]
        # Sample analysis: data table
        layouts = project.experiment_layouts
        sample_data_table_headers = [
            "plate",
            "well",
            "sample",
            "barcode",
            "protein",
            "type",
            "allele",
            "allele fraction",
            "frame",
            "variant Type"]
        sample_data_table_rows = []
        for layout in layouts:
            for well in layout.wells:
                for slc in well.sequencing_library_contents:
                    for vc in slc.variant_results:
                        row = []
                        row.append(layout.geid)
                        row.append("{:s}{:02}".format(well.row, well.column))
                        row.append(slc.sequencing_sample_name)
                        row.append(slc.sequencing_barcode)
                        row.append(vc.protein_effect)
                        row.append(vc.consequence)
                        row.append(vc.alleles)
                        row.append("{0:.3f}".format(vc.allele_fraction))
                        row.append(vc.frame)
                        row.append(vc.variant_type)
                        sample_data_table_rows.append(row)

        return dict(project=project,
                    title="Genome Editing Core",
                    subtitle="Project: {}".format(project.geid),
                    cellgrowthplot=plotter.growth_plot(),
                    proteinabundanceplot=plotter.abundance_plot(),
                    ngsplot=ngsplotter.combined_ngs_plot(),
                    project_headers=project_headers,
                    project_rows=project_rows,
                    target_headers=target_headers,
                    target_rows=target_rows,
                    guide_headers=guide_headers,
                    guide_rows=guide_rows,
                    guide_mismatch_headers=guide_mismatch_headers,
                    guide_mismatch_rows=guide_mismatch_rows,
                    sample_data_table_headers=sample_data_table_headers,
                    sample_data_table_rows=sample_data_table_rows)

    @view_config(route_name="project_edit", renderer="../templates/project/editproject.pt")
    def edit_project(self):
        id = self.request.matchdict['projectid']
        project = self.dbsession.query(Project).filter(Project.id == id).one()
        title = "Genome Editing Core"
        subtitle = "Project: {}".format(project.geid)
        edit_form = self.projects_form("Update")
        if 'submit' in self.request.params:
            fields = self.request.POST.items()
            try:
                appstruct = edit_form.validate(fields)
            except deform.ValidationFailure as e:
                return dict(project=project, form=e.render(), title=title, subtitle=subtitle)
            print("New comments = %s" % appstruct['comments'])
            project.comments = appstruct['comments']
            url = self.request.route_url('project_view', projectid=project.id)
            return HTTPFound(url)
        return dict(title=title,
                    subtitle=subtitle,
                    projectid=project.id,
                    project=project,)
