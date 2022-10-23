$("input").filepond({
    allowMultiple: true,
    allowRevert: false,
    allowRemove: false,
    server: {
        process: '/upload/process',
    },
})
