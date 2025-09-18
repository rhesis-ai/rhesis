export default {
  primaryHue: 210,
  primarySaturation: 100,
  toc: {
    float: true,
    title: 'On This Page',
  },
  sidebar: {
    titleComponent: ({ title, type }) => {
      if (type === 'separator') {
        return <span className="cursor-default">{title}</span>
      }
      return <>{title}</>
    },
    defaultMenuCollapseLevel: 1,
    autoCollapse: true,
    toggleButton: true,
  },
  feedback: {
    content: 'Question? Give us feedback →',
    labels: 'feedback'
  },
  editLink: {
    text: 'Edit this page on GitHub →'
  }
}