import React from 'react';

const ProjectGallery = () => {
  const projects = [
    {
      id: 1,
      title: 'Minimalist Studio Apartment',
      description: 'A complete redesign of a 400 sq ft studio using space-saving furniture from IKEA.',
      image: '🛋️',
      tags: ['Minimalist', 'Studio', 'IKEA'],
      date: 'May 10, 2026'
    },
    {
      id: 2,
      title: 'Industrial Loft Workspace',
      description: 'Converted an open loft into a productive workspace with raw materials and Alibaba finds.',
      image: '🏢',
      tags: ['Industrial', 'Office', 'Alibaba'],
      date: 'May 8, 2026'
    },
    {
      id: 3,
      title: 'Scandinavian Bedroom Retreat',
      description: 'Cozy and bright bedroom design focusing on natural light and wooden textures.',
      image: '🛏️',
      tags: ['Scandinavian', 'Bedroom', 'Mixed'],
      date: 'May 5, 2026'
    },
    {
      id: 4,
      title: 'Modern Luxury Living Room',
      description: 'High-end living room concept with premium finishes and smart home integration.',
      image: '📺',
      tags: ['Luxury', 'Living Room', 'Premium'],
      date: 'May 1, 2026'
    }
  ];

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Project Gallery</h2>
        <p className="mt-4 text-lg text-slate-500">
          Explore stunning interior designs and layouts generated entirely by our AI engine.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {projects.map((project) => (
          <div key={project.id} className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-lg transition-shadow duration-300 flex flex-col">
            <div className="h-48 bg-slate-100 flex items-center justify-center text-6xl border-b border-slate-100">
              {project.image}
            </div>
            <div className="p-6 flex-1 flex flex-col">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-xl font-bold text-slate-800">{project.title}</h3>
                <span className="text-xs font-medium text-slate-400 bg-slate-100 px-2 py-1 rounded-md">
                  {project.date}
                </span>
              </div>
              <p className="text-slate-600 mb-6 flex-1">{project.description}</p>
              <div className="flex flex-wrap gap-2 mt-auto">
                {project.tags.map((tag, index) => (
                  <span key={index} className="px-3 py-1 bg-brand-50 text-brand-700 text-xs font-semibold rounded-full border border-brand-100">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-12 text-center">
        <button className="btn-primary px-8 py-3 text-lg shadow-md hover:shadow-lg transition-all">
          Generate Your Own Design
        </button>
      </div>
    </div>
  );
};

export default ProjectGallery;